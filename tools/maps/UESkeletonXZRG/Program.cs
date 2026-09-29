using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Animation;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Dto;
using System.Text;
using System.Text.Json;

const uint XzrgVersion = 1;
const uint XzrgHeaderBytes = 48;
const uint XzrgBoneBytes = 56;
const uint FlagXzielBasis = 1u << 0;

if (args.Length is < 4 or > 6)
{
    Console.Error.WriteLine(
        "usage: UESkeletonXZRG <unpacked-root> <mappings.usmap> <class-census.json> <output-dir> [max-skeletons] [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputDir = args[3];
var maxSkeletons =
    args.Length >= 5
        ? int.Parse(args[4])
        : 8;
var sourceGameName =
    args.Length >= 6
        ? args[5]
        : "ue5.1";

if (maxSkeletons <= 0)
    throw new ArgumentOutOfRangeException(
        nameof(maxSkeletons));

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" =>
            EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" =>
            EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " +
            sourceGameName)
    };

using var censusDoc =
    JsonDocument.Parse(
        File.ReadAllText(censusPath));

var candidatePackages =
    censusDoc.RootElement
        .GetProperty("packages")
        .EnumerateArray()
        .Where(row =>
            row.GetProperty("classes")
                .TryGetProperty(
                    "Skeleton",
                    out var count) &&
            count.GetInt32() > 0)
        .Select(row =>
            NormalizeMergedShardPath(
                row.GetProperty("packagePath")
                    .GetString()
                ?? throw new InvalidDataException(
                    "packagePath missing")))
        .Distinct(
            StringComparer.OrdinalIgnoreCase)
        .OrderBy(
            x => x,
            StringComparer.OrdinalIgnoreCase)
        .ToArray();

var provider =
    new DefaultFileProvider(
        root,
        SearchOption.AllDirectories,
        new VersionContainer(sourceGame),
        StringComparer.OrdinalIgnoreCase)
    {
        MappingsContainer =
            new FileUsmapTypeMappingsProvider(
                mappingsPath)
    };

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

Directory.CreateDirectory(outputDir);

var rows = new List<object>();
var failures = new List<object>();
var topologyHashes =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);
var poseHashes =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);

var converted = 0;
long totalBones = 0;
long totalFileBytes = 0;

foreach (var logicalPackage in
         candidatePackages)
{
    if (converted >= maxSkeletons)
        break;

    var resolvedPath =
        ResolveProviderPackagePath(
            provider,
            logicalPackage);

    if (resolvedPath is null)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package =
            provider.LoadPackage(
                resolvedPath);

        var skeletons =
            package.GetExports()
                .OfType<USkeleton>()
                .OrderBy(
                    skeleton => skeleton.Name,
                    StringComparer.Ordinal)
                .ToArray();

        foreach (var skeleton in skeletons)
        {
            if (converted >= maxSkeletons)
                break;

            try
            {
                using var dto =
                    new SkeletonDto(
                        skeleton);

                var fileName =
                    $"r{converted:D4}.xrg";
                var outPath =
                    Path.Combine(
                        outputDir,
                        fileName);

                var result =
                    WriteXzrg(
                        outPath,
                        dto);

                rows.Add(new {
                    index = converted,
                    file = fileName,
                    packagePath = logicalPackage,
                    resolvedPackagePath =
                        resolvedPath,
                    objectPath =
                        skeleton.GetPathName(),
                    result.bones,
                    skeletonHash =
                        result.skeletonHash
                            .ToString("x16"),
                    poseHash =
                        result.poseHash
                            .ToString("x16"),
                    result.fileBytes
                });

                converted++;
                totalBones += result.bones;
                totalFileBytes +=
                    result.fileBytes;

                var topology =
                    result.skeletonHash
                        .ToString("x16");
                topologyHashes[topology] =
                    topologyHashes
                        .GetValueOrDefault(
                            topology) + 1;

                var pose =
                    result.poseHash
                        .ToString("x16");
                poseHashes[pose] =
                    poseHashes
                        .GetValueOrDefault(
                            pose) + 1;
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = logicalPackage,
                    objectPath =
                        skeleton.GetPathName(),
                    error =
                        e.GetType().FullName +
                        ": " +
                        e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error =
                e.GetType().FullName +
                ": " +
                e.Message
        });
    }
}

var ready =
    converted == maxSkeletons &&
    rows.Count == maxSkeletons &&
    failures.Count == 0 &&
    totalBones > 0 &&
    totalFileBytes > 0 &&
    topologyHashes.Count > 0 &&
    poseHashes.Count > 0;

var report = new {
    schemaVersion = 1,
    format = "xziel_rig_xzrg_v1",
    sourceGameName,
    requestedSkeletons = maxSkeletons,
    convertedSkeletons = converted,
    totalBones,
    skeletonHashCounts = topologyHashes,
    poseHashCounts = poseHashes,
    totalFileBytes,
    failureCount = failures.Count,
    skeletons = rows,
    failures,
    ready
};

File.WriteAllText(
    Path.Combine(
        outputDir,
        "report.json"),
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_UE_XZRG_PROBE " +
    JsonSerializer.Serialize(new {
        requested = maxSkeletons,
        converted,
        totalBones,
        topologyHashes =
            topologyHashes.Count,
        poseHashes =
            poseHashes.Count,
        totalFileBytes,
        failures = failures.Count,
        ready
    }));

foreach (var failure in
         failures.Take(100))
{
    Console.WriteLine(
        "XZIEL_UE_XZRG_FAILURE " +
        JsonSerializer.Serialize(
            failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_XZRG_PROBE_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_XZRG_PROBE_GREEN");
return 0;

static (
    int bones,
    ulong skeletonHash,
    ulong poseHash,
    long fileBytes
) WriteXzrg(
    string outputPath,
    SkeletonDto dto)
{
    var bones =
        dto.Bones;

    if (bones.Length == 0)
        throw new InvalidDataException(
            "skeleton has no bones");

    if (bones.Length > ushort.MaxValue)
        throw new InvalidDataException(
            $"skeleton has too many bones: {bones.Length}");

    var skeletonHash =
        XzielSkeletonIdentity.HashTopology(
            bones);
    var poseHash =
        XzielSkeletonIdentity.HashBones(
            bones);

    var strings =
        new MemoryStream();
    var names =
        new (uint offset, uint bytes)[
            bones.Length];

    for (var i = 0;
         i < bones.Length;
         ++i)
    {
        var encoded =
            Encoding.UTF8.GetBytes(
                bones[i].Name);

        if (encoded.Length == 0)
            throw new InvalidDataException(
                $"bone {i} has empty name");

        names[i] = (
            checked((uint)strings.Position),
            checked((uint)encoded.Length));
        strings.Write(encoded);
    }

    var boneOffset =
        XzrgHeaderBytes;
    var stringOffset =
        checked(
            boneOffset +
            checked((uint)bones.Length) *
                XzrgBoneBytes);
    var stringBytes =
        checked((uint)strings.Length);
    var fileBytes =
        checked(
            (long)stringOffset +
            stringBytes);

    if (fileBytes > uint.MaxValue)
        throw new InvalidDataException(
            $"XZRG v1 file exceeds 32-bit offsets: {fileBytes}");

    Directory.CreateDirectory(
        Path.GetDirectoryName(
            Path.GetFullPath(
                outputPath))!);

    using var stream =
        new FileStream(
            outputPath,
            FileMode.Create,
            FileAccess.Write,
            FileShare.None);
    using var writer =
        new BinaryWriter(
            stream,
            Encoding.UTF8,
            leaveOpen: true);

    writer.Write((byte)'X');
    writer.Write((byte)'Z');
    writer.Write((byte)'R');
    writer.Write((byte)'G');
    writer.Write(XzrgVersion);
    writer.Write(FlagXzielBasis);
    writer.Write(
        checked((uint)bones.Length));
    writer.Write(XzrgBoneBytes);
    writer.Write(boneOffset);
    writer.Write(stringOffset);
    writer.Write(stringBytes);
    writer.Write(0u);
    writer.Write(skeletonHash);
    writer.Write(poseHash);

    if (stream.Position !=
        XzrgHeaderBytes)
    {
        throw new InvalidDataException(
            $"XZRG header size mismatch: {stream.Position}");
    }

    for (var i = 0;
         i < bones.Length;
         ++i)
    {
        var bone = bones[i];
        var rotation =
            XzielSkeletonIdentity
                .RotationToXziel(
                    bone.Transform.Rotation);
        var translation =
            XzielSkeletonIdentity
                .PositionToXziel(
                    bone.Transform.Translation);
        var scale =
            bone.Transform.Scale3D;

        writer.Write(bone.ParentIndex);
        writer.Write(names[i].offset);
        writer.Write(names[i].bytes);
        writer.Write(0u);

        writer.Write(rotation.X);
        writer.Write(rotation.Y);
        writer.Write(rotation.Z);
        writer.Write(rotation.W);

        writer.Write(translation.X);
        writer.Write(translation.Y);
        writer.Write(translation.Z);

        writer.Write(scale.X);
        writer.Write(scale.Y);
        writer.Write(scale.Z);
    }

    writer.Write(strings.ToArray());
    writer.Flush();

    if (stream.Length != fileBytes)
        throw new InvalidDataException(
            $"XZRG size mismatch expected={fileBytes} actual={stream.Length}");

    return (
        bones.Length,
        skeletonHash,
        poseHash,
        fileBytes);
}

static string NormalizeMergedShardPath(
    string path)
{
    var normalized =
        path.Replace('\', '/');

    if (!normalized.StartsWith(
            "shard-",
            StringComparison.OrdinalIgnoreCase))
        return normalized;

    var slash =
        normalized.IndexOf('/');

    if (slash <= 6)
        return normalized;

    var shardNumber =
        normalized.AsSpan(
            6,
            slash - 6);

    for (var i = 0;
         i < shardNumber.Length;
         ++i)
    {
        if (!char.IsDigit(
                shardNumber[i]))
            return normalized;
    }

    return normalized[(slash + 1)..];
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized =
        logicalPath
            .Replace('\', '/')
            .TrimStart('/');

    if (provider.Files.ContainsKey(
            normalized))
        return normalized;

    var matches =
        provider.Files.Keys
            .Where(key =>
                key.EndsWith(
                    normalized,
                    StringComparison.OrdinalIgnoreCase))
            .OrderBy(
                key => key.Length)
            .ThenBy(
                key => key,
                StringComparer.OrdinalIgnoreCase)
            .Take(2)
            .ToArray();

    return matches.Length == 1
        ? matches[0]
        : null;
}
