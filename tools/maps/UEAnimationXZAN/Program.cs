using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Animation;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Animations;
using CUE4Parse_Conversion.Dto;
using System.Text;
using System.Text.Json;

const uint XzanVersion = 1;
const uint XzanHeaderBytes = 56;
const uint XzanTrackBytes = 56;
const uint FlagXzielBasis = 1u << 0;
const uint FlagAdditive = 1u << 1;

if (args.Length is < 4 or > 6)
{
    Console.Error.WriteLine(
        "usage: UEAnimationXZAN <unpacked-root> <mappings.usmap> <class-census.json> <output-dir> [max-anims] [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputDir = args[3];
var maxAnimations =
    args.Length >= 5
        ? int.Parse(args[4])
        : 8;
var sourceGameName =
    args.Length >= 6
        ? args[5]
        : "ue5.1";

if (maxAnimations <= 0)
    throw new ArgumentOutOfRangeException(
        nameof(maxAnimations));

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
                    "AnimSequence",
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

var provider = new DefaultFileProvider(
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
var hashes =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);

var converted = 0;
long totalFrames = 0;
long totalTracks = 0;
long positionKeys = 0;
long rotationKeys = 0;
long scaleKeys = 0;
long sharedTimeKeys = 0;
long positionTimeKeys = 0;
long rotationTimeKeys = 0;
long scaleTimeKeys = 0;
long totalFileBytes = 0;
var additiveCount = 0;

foreach (var logicalPackage in candidatePackages)
{
    if (converted >= maxAnimations)
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

        var animations =
            package.GetExports()
                .OfType<UAnimSequence>()
                .OrderBy(
                    animation => animation.Name,
                    StringComparer.Ordinal)
                .ToArray();

        foreach (var animation in animations)
        {
            if (converted >= maxAnimations)
                break;

            try
            {
                var skeleton =
                    ResolveAnimationSkeleton(
                        provider,
                        animation,
                        out var skeletonPackagePath);

                using var skeletonDto =
                    new SkeletonDto(skeleton);

                var skeletonHash =
                    XzielSkeletonIdentity.HashTopology(
                        skeletonDto.Bones);

                var convertedSet =
                    skeleton.ConvertAnims(
                        animation);

                if (convertedSet.Sequences.Count != 1)
                    throw new InvalidDataException(
                        $"animation conversion produced {convertedSet.Sequences.Count} sequences");

                var sequence =
                    convertedSet.Sequences[0];

                var fileName =
                    $"a{converted:D4}.xan";
                var outPath =
                    Path.Combine(
                        outputDir,
                        fileName);

                var result =
                    WriteXzan(
                        outPath,
                        sequence,
                        skeletonHash);

                rows.Add(new {
                    index = converted,
                    file = fileName,
                    packagePath = logicalPackage,
                    resolvedPackagePath =
                        resolvedPath,
                    objectPath =
                        animation.GetPathName(),
                    skeletonPackagePath,
                    skeletonHash =
                        skeletonHash
                            .ToString("x16"),
                    result.frames,
                    result.framesPerSecond,
                    result.durationSeconds,
                    result.tracks,
                    result.positionKeys,
                    result.rotationKeys,
                    result.scaleKeys,
                    result.sharedTimeKeys,
                    result.positionTimeKeys,
                    result.rotationTimeKeys,
                    result.scaleTimeKeys,
                    result.additive,
                    result.fileBytes
                });

                converted++;
                totalFrames += result.frames;
                totalTracks += result.tracks;
                positionKeys +=
                    result.positionKeys;
                rotationKeys +=
                    result.rotationKeys;
                scaleKeys +=
                    result.scaleKeys;
                sharedTimeKeys +=
                    result.sharedTimeKeys;
                positionTimeKeys +=
                    result.positionTimeKeys;
                rotationTimeKeys +=
                    result.rotationTimeKeys;
                scaleTimeKeys +=
                    result.scaleTimeKeys;
                totalFileBytes +=
                    result.fileBytes;
                if (result.additive)
                    additiveCount++;

                var hash =
                    skeletonHash
                        .ToString("x16");
                hashes[hash] =
                    hashes.GetValueOrDefault(hash) + 1;
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = logicalPackage,
                    objectPath =
                        animation.GetPathName(),
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
    converted == maxAnimations &&
    rows.Count == maxAnimations &&
    failures.Count == 0 &&
    totalFrames > 0 &&
    totalTracks > 0 &&
    positionKeys + rotationKeys + scaleKeys > 0 &&
    totalFileBytes > 0 &&
    hashes.Count > 0;

var report = new {
    schemaVersion = 1,
    format = "xziel_animation_xzan_v1",
    sourceGameName,
    requestedAnimations = maxAnimations,
    convertedAnimations = converted,
    totalFrames,
    totalTracks,
    positionKeys,
    rotationKeys,
    scaleKeys,
    sharedTimeKeys,
    positionTimeKeys,
    rotationTimeKeys,
    scaleTimeKeys,
    additiveCount,
    skeletonHashCounts = hashes,
    totalFileBytes,
    failureCount = failures.Count,
    animations = rows,
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
    "XZIEL_UE_XZAN_PROBE " +
    JsonSerializer.Serialize(new {
        requested = maxAnimations,
        converted,
        totalFrames,
        totalTracks,
        positionKeys,
        rotationKeys,
        scaleKeys,
        sharedTimeKeys,
        positionTimeKeys,
        rotationTimeKeys,
        scaleTimeKeys,
        additiveCount,
        skeletons = hashes.Count,
        totalFileBytes,
        failures = failures.Count,
        ready
    }));

foreach (var failure in failures.Take(100))
{
    Console.WriteLine(
        "XZIEL_UE_XZAN_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_XZAN_PROBE_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_XZAN_PROBE_GREEN");
return 0;

static (
    int frames,
    float framesPerSecond,
    float durationSeconds,
    int tracks,
    long positionKeys,
    long rotationKeys,
    long scaleKeys,
    long sharedTimeKeys,
    long positionTimeKeys,
    long rotationTimeKeys,
    long scaleTimeKeys,
    bool additive,
    long fileBytes
) WriteXzan(
    string outputPath,
    CUE4Parse_Conversion.Writers.ActorX.Structs.Animations.CAnimSequence sequence,
    ulong skeletonHash)
{
    if (sequence.NumFrames <= 0)
        throw new InvalidDataException(
            "animation has no frames");

    if (!float.IsFinite(
            sequence.FramesPerSecond) ||
        sequence.FramesPerSecond <= 0.0f)
    {
        throw new InvalidDataException(
            $"invalid animation FPS {sequence.FramesPerSecond}");
    }

    if (!float.IsFinite(
            sequence.AnimEndTime) ||
        sequence.AnimEndTime <= 0.0f)
    {
        throw new InvalidDataException(
            $"invalid animation duration {sequence.AnimEndTime}");
    }

    if (sequence.Tracks.Count == 0)
        throw new InvalidDataException(
            "animation has no tracks");

    if (skeletonHash == 0UL)
        throw new InvalidDataException(
            "animation skeleton hash is zero");

    using var payload =
        new MemoryStream();
    var records =
        new TrackRecord[
            sequence.Tracks.Count];

    long totalPositionKeys = 0;
    long totalRotationKeys = 0;
    long totalScaleKeys = 0;
    long totalSharedTimes = 0;
    long totalPositionTimes = 0;
    long totalRotationTimes = 0;
    long totalScaleTimes = 0;

    for (var trackIndex = 0;
         trackIndex < sequence.Tracks.Count;
         ++trackIndex)
    {
        var track =
            sequence.Tracks[trackIndex];

        // CUE4Parse emits one track per skeleton bone. A bone can have no
        // authored transform keys; Unreal then evaluates that bone from the
        // skeleton reference pose. Preserve that as a zero-count XZAN track
        // rather than fabricating keys or rejecting a valid animation.
        var posOffset =
            checked((uint)payload.Position);
        foreach (var key in track.KeyPos)
        {
            var value =
                XzielSkeletonIdentity.PositionToXziel(
                    key);
            WriteFinite(payload, value.X);
            WriteFinite(payload, value.Y);
            WriteFinite(payload, value.Z);
        }

        var rotOffset =
            checked((uint)payload.Position);
        foreach (var key in track.KeyQuat)
        {
            var value =
                XzielSkeletonIdentity.RotationToXziel(
                    key);
            WriteFinite(payload, value.X);
            WriteFinite(payload, value.Y);
            WriteFinite(payload, value.Z);
            WriteFinite(payload, value.W);
        }

        var scaleOffset =
            checked((uint)payload.Position);
        foreach (var key in track.KeyScale)
        {
            WriteFinite(payload, key.X);
            WriteFinite(payload, key.Y);
            WriteFinite(payload, key.Z);
        }

        var sharedTimeOffset =
            checked((uint)payload.Position);
        WriteTimes(
            payload,
            track.KeyTime,
            sequence.NumFrames,
            trackIndex,
            "shared");

        var posTimeOffset =
            checked((uint)payload.Position);
        WriteTimes(
            payload,
            track.KeyPosTime,
            sequence.NumFrames,
            trackIndex,
            "position");

        var rotTimeOffset =
            checked((uint)payload.Position);
        WriteTimes(
            payload,
            track.KeyQuatTime,
            sequence.NumFrames,
            trackIndex,
            "rotation");

        var scaleTimeOffset =
            checked((uint)payload.Position);
        WriteTimes(
            payload,
            track.KeyScaleTime,
            sequence.NumFrames,
            trackIndex,
            "scale");

        records[trackIndex] =
            new TrackRecord(
                checked((uint)track.KeyPos.Length),
                checked((uint)track.KeyQuat.Length),
                checked((uint)track.KeyScale.Length),
                checked((uint)track.KeyTime.Length),
                checked((uint)track.KeyPosTime.Length),
                checked((uint)track.KeyQuatTime.Length),
                checked((uint)track.KeyScaleTime.Length),
                posOffset,
                rotOffset,
                scaleOffset,
                sharedTimeOffset,
                posTimeOffset,
                rotTimeOffset,
                scaleTimeOffset);

        totalPositionKeys +=
            track.KeyPos.Length;
        totalRotationKeys +=
            track.KeyQuat.Length;
        totalScaleKeys +=
            track.KeyScale.Length;
        totalSharedTimes +=
            track.KeyTime.Length;
        totalPositionTimes +=
            track.KeyPosTime.Length;
        totalRotationTimes +=
            track.KeyQuatTime.Length;
        totalScaleTimes +=
            track.KeyScaleTime.Length;
    }

    var payloadBytes =
        checked((uint)payload.Length);
    var trackOffset =
        XzanHeaderBytes;
    var payloadOffset =
        checked(
            trackOffset +
            checked((uint)records.Length) *
                XzanTrackBytes);
    var fileBytes =
        checked(
            (long)payloadOffset +
            payloadBytes);

    if (fileBytes > uint.MaxValue)
        throw new InvalidDataException(
            $"XZAN v1 file exceeds 32-bit offsets: {fileBytes}");

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
    writer.Write((byte)'A');
    writer.Write((byte)'N');
    writer.Write(XzanVersion);
    writer.Write(
        FlagXzielBasis |
        (sequence.IsAdditive
            ? FlagAdditive
            : 0u));
    writer.Write(
        checked((uint)sequence.NumFrames));
    writer.Write(sequence.FramesPerSecond);
    writer.Write(sequence.AnimEndTime);
    writer.Write(
        checked((uint)records.Length));
    writer.Write(XzanTrackBytes);
    writer.Write(trackOffset);
    writer.Write(payloadOffset);
    writer.Write(payloadBytes);
    writer.Write(0u);
    writer.Write(skeletonHash);

    if (stream.Position != XzanHeaderBytes)
        throw new InvalidDataException(
            $"XZAN header size mismatch: {stream.Position}");

    foreach (var record in records)
    {
        writer.Write(record.PosCount);
        writer.Write(record.RotCount);
        writer.Write(record.ScaleCount);
        writer.Write(record.SharedTimeCount);
        writer.Write(record.PosTimeCount);
        writer.Write(record.RotTimeCount);
        writer.Write(record.ScaleTimeCount);
        writer.Write(record.PosOffset);
        writer.Write(record.RotOffset);
        writer.Write(record.ScaleOffset);
        writer.Write(record.SharedTimeOffset);
        writer.Write(record.PosTimeOffset);
        writer.Write(record.RotTimeOffset);
        writer.Write(record.ScaleTimeOffset);
    }

    payload.Position = 0;
    payload.CopyTo(stream);
    writer.Flush();

    if (stream.Length != fileBytes)
        throw new InvalidDataException(
            $"XZAN size mismatch expected={fileBytes} actual={stream.Length}");

    return (
        sequence.NumFrames,
        sequence.FramesPerSecond,
        sequence.AnimEndTime,
        sequence.Tracks.Count,
        totalPositionKeys,
        totalRotationKeys,
        totalScaleKeys,
        totalSharedTimes,
        totalPositionTimes,
        totalRotationTimes,
        totalScaleTimes,
        sequence.IsAdditive,
        fileBytes);
}

static void WriteTimes(
    Stream stream,
    IReadOnlyList<float> times,
    int frameCount,
    int trackIndex,
    string kind)
{
    var previous = -1.0f;

    for (var i = 0;
         i < times.Count;
         ++i)
    {
        var value = times[i];

        if (!float.IsFinite(value) ||
            value < 0.0f ||
            value > frameCount ||
            (i > 0 && value < previous))
        {
            throw new InvalidDataException(
                $"animation track {trackIndex} {kind} time[{i}]={value} is invalid for {frameCount} frames");
        }

        WriteFinite(
            stream,
            value);
        previous = value;
    }
}

static void WriteFinite(
    Stream stream,
    float value)
{
    if (!float.IsFinite(value))
        throw new InvalidDataException(
            "animation contains non-finite key value");

    Span<byte> bytes =
        stackalloc byte[4];

    BitConverter.TryWriteBytes(
        bytes,
        value);

    if (!BitConverter.IsLittleEndian)
        bytes.Reverse();

    stream.Write(bytes);
}

static USkeleton ResolveAnimationSkeleton(
    DefaultFileProvider provider,
    UAnimSequence animation,
    out string sourcePackagePath)
{
    var resolved =
        animation.Skeleton?.ResolvedObjectNoCache
        ?? throw new InvalidDataException(
            "animation has no resolvable Skeleton object reference");

    var objectPath =
        resolved.GetPathName();

    if (string.IsNullOrWhiteSpace(
            objectPath))
    {
        throw new InvalidDataException(
            "animation Skeleton reference has no object path");
    }

    var dot =
        objectPath.LastIndexOf('.');
    var virtualPackagePath =
        (dot > 0
            ? objectPath[..dot]
            : objectPath)
        .Replace('\\', '/')
        .Trim();

    var objectName =
        dot > 0 &&
        dot + 1 < objectPath.Length
            ? objectPath[(dot + 1)..]
            : virtualPackagePath
                .Split('/')
                .Last();

    var normalizedVirtual =
        virtualPackagePath
            .TrimStart('/');

    var candidates =
        new List<string>
        {
            normalizedVirtual + ".uasset"
        };

    var firstSlash =
        normalizedVirtual
            .IndexOf('/');

    if (firstSlash > 0 &&
        firstSlash + 1 <
            normalizedVirtual.Length)
    {
        var mountName =
            normalizedVirtual[
                ..firstSlash];
        var mountRelative =
            normalizedVirtual[
                (firstSlash + 1)..];

        if (mountName.Equals(
                "Game",
                StringComparison.OrdinalIgnoreCase))
        {
            candidates.Add(
                $"Content/{mountRelative}.uasset");
        }
        else if (mountName.Equals(
                     "Engine",
                     StringComparison.OrdinalIgnoreCase))
        {
            candidates.Add(
                $"Engine/Content/{mountRelative}.uasset");
        }
        else
        {
            candidates.Add(
                $"Plugins/{mountName}/Content/{mountRelative}.uasset");
        }
    }

    string? providerKey = null;

    foreach (var suffix in
             candidates.Distinct(
                 StringComparer.OrdinalIgnoreCase))
    {
        var matches =
            provider.Files.Keys
                .Where(key =>
                    key.EndsWith(
                        suffix,
                        StringComparison.OrdinalIgnoreCase))
                .OrderBy(
                    key => key.Length)
                .ThenBy(
                    key => key,
                    StringComparer.OrdinalIgnoreCase)
                .Take(2)
                .ToArray();

        if (matches.Length == 1)
        {
            providerKey = matches[0];
            break;
        }

        if (matches.Length > 1)
        {
            throw new InvalidDataException(
                $"ambiguous Skeleton package resolution for {objectPath}: " +
                string.Join(", ", matches));
        }
    }

    if (providerKey is null)
    {
        throw new FileNotFoundException(
            $"Skeleton package unresolved for {objectPath}; tried " +
            string.Join(", ", candidates));
    }

    sourcePackagePath =
        providerKey;

    var package =
        provider.LoadPackage(
            providerKey);

    var skeletons =
        package.GetExports()
            .OfType<USkeleton>()
            .ToArray();

    var exact =
        skeletons
            .Where(skeleton =>
                string.Equals(
                    skeleton.Name,
                    objectName,
                    StringComparison.OrdinalIgnoreCase))
            .ToArray();

    if (exact.Length == 1)
        return exact[0];

    if (exact.Length > 1)
    {
        throw new InvalidDataException(
            $"multiple Skeleton exports named {objectName} in {providerKey}");
    }

    if (skeletons.Length == 1)
        return skeletons[0];

    throw new InvalidDataException(
        $"Skeleton export {objectName} unresolved in {providerKey}; decoded skeleton exports={skeletons.Length}");
}

static string NormalizeMergedShardPath(
    string path)
{
    var normalized =
        path.Replace('\\', '/');

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

    return normalized[
        (slash + 1)..];
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized =
        logicalPath
            .Replace('\\', '/')
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

sealed record TrackRecord(
    uint PosCount,
    uint RotCount,
    uint ScaleCount,
    uint SharedTimeCount,
    uint PosTimeCount,
    uint RotTimeCount,
    uint ScaleTimeCount,
    uint PosOffset,
    uint RotOffset,
    uint ScaleOffset,
    uint SharedTimeOffset,
    uint PosTimeOffset,
    uint RotTimeOffset,
    uint ScaleTimeOffset);
