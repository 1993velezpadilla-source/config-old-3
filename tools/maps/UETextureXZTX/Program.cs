using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Versions;
using System.Text;
using System.Text.Json;

const uint XztxVersion = 1;
const uint XztxHeaderBytes = 80;
const uint XztxMipRecordBytes = 24;
const uint XztxFormatNameBytes = 32;
const uint FlagSrgb = 1u << 0;

if (args.Length is < 4 or > 6)
{
    Console.Error.WriteLine(
        "usage: UETextureXZTX <unpacked-root> <mappings.usmap> <class-census.json> <output-dir> [max-textures] [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputDir = args[3];
var maxTextures =
    args.Length >= 5
        ? int.Parse(args[4])
        : 8;
var sourceGameName =
    args.Length >= 6
        ? args[5]
        : "ue5.1";

if (maxTextures <= 0)
    throw new ArgumentOutOfRangeException(nameof(maxTextures));

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
                .EnumerateObject()
                .Any(property =>
                    property.Name.EndsWith(
                        "Texture2D",
                        StringComparison.Ordinal) &&
                    property.Value.GetInt32() > 0))
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
var formats =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);

var converted = 0;
long totalMips = 0;
long totalPayloadBytes = 0;
long totalFileBytes = 0;

foreach (var logicalPackage in candidatePackages)
{
    if (converted >= maxTextures)
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

        var textures =
            package.GetExports()
                .OfType<UTexture2D>()
                .OrderBy(
                    texture => texture.Name,
                    StringComparer.Ordinal)
                .ToArray();

        foreach (var texture in textures)
        {
            if (converted >= maxTextures)
                break;

            try
            {
                var fileName =
                    $"t{converted:D4}.xzt";
                var outPath =
                    Path.Combine(
                        outputDir,
                        fileName);

                var result =
                    WriteXztx(
                        outPath,
                        texture);

                rows.Add(new {
                    index = converted,
                    file = fileName,
                    packagePath = logicalPackage,
                    resolvedPackagePath =
                        resolvedPath,
                    objectPath =
                        texture.GetPathName(),
                    sourcePlatformWidth =
                        texture.PlatformData.SizeX,
                    sourcePlatformHeight =
                        texture.PlatformData.SizeY,
                    result.width,
                    result.height,
                    result.depth,
                    result.mipCount,
                    result.format,
                    result.srgb,
                    result.payloadBytes,
                    result.fileBytes
                });

                converted++;
                totalMips += result.mipCount;
                totalPayloadBytes +=
                    result.payloadBytes;
                totalFileBytes +=
                    result.fileBytes;

                formats[result.format] =
                    formats.GetValueOrDefault(
                        result.format) + 1;
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = logicalPackage,
                    objectPath =
                        texture.GetPathName(),
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
    converted == maxTextures &&
    rows.Count == maxTextures &&
    failures.Count == 0 &&
    totalMips > 0 &&
    totalPayloadBytes > 0 &&
    totalFileBytes > totalPayloadBytes;

var report = new {
    schemaVersion = 1,
    format = "xziel_texture_xztx_v1",
    sourceGameName,
    requestedTextures = maxTextures,
    convertedTextures = converted,
    totalMips,
    totalPayloadBytes,
    totalFileBytes,
    formatCounts = formats,
    failureCount = failures.Count,
    textures = rows,
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
    "XZIEL_UE_XZTX_PROBE " +
    JsonSerializer.Serialize(new {
        requested = maxTextures,
        converted,
        totalMips,
        totalPayloadBytes,
        totalFileBytes,
        formats,
        failures = failures.Count,
        ready
    }));

foreach (var failure in failures.Take(50))
{
    Console.WriteLine(
        "XZIEL_UE_XZTX_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_XZTX_PROBE_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_XZTX_PROBE_GREEN");
return 0;

static (
    int width,
    int height,
    int depth,
    int mipCount,
    string format,
    bool srgb,
    long payloadBytes,
    long fileBytes
) WriteXztx(
    string outputPath,
    UTexture2D texture)
{
    var format =
        texture.Format.ToString();

    if (string.IsNullOrWhiteSpace(format) ||
        format == "PF_Unknown")
        throw new InvalidDataException(
            "texture pixel format unresolved");

    var formatBytes =
        Encoding.ASCII.GetBytes(format);

    if (formatBytes.Length == 0 ||
        formatBytes.Length >=
            XztxFormatNameBytes)
        throw new InvalidDataException(
            $"XZTX format name too long: {format}");

    var mipCount =
        texture.PlatformData.Mips.Length;

    if (mipCount <= 0)
        throw new InvalidDataException(
            "texture has no cooked mips");

    var mips =
        new List<(
            int sourceIndex,
            int width,
            int height,
            int depth,
            byte[] data)>(
                mipCount);

    for (var i = 0;
         i < mipCount;
         ++i)
    {
        var mip =
            texture.GetMip(i)
            ?? throw new InvalidDataException(
                $"mip {i} unresolved");

        var data = mip.BulkData?.Data;
        if (data is null ||
            data.Length == 0)
        {
            throw new InvalidDataException(
                $"mip {i} has no payload");
        }

        if (mip.SizeX <= 0 ||
            mip.SizeY <= 0 ||
            mip.SizeZ <= 0)
        {
            throw new InvalidDataException(
                $"mip {i} invalid dimensions " +
                $"{mip.SizeX}x{mip.SizeY}x{mip.SizeZ}");
        }

        mips.Add((
            i,
            mip.SizeX,
            mip.SizeY,
            mip.SizeZ,
            data));
    }

    var first = mips[0];

    long payloadBytes =
        mips.Sum(
            mip => (long)mip.data.Length);

    long payloadOffset =
        checked(
            (long)XztxHeaderBytes +
            (long)mips.Count *
                XztxMipRecordBytes);

    long fileBytes =
        checked(
            payloadOffset +
            payloadBytes);

    if (fileBytes > uint.MaxValue)
        throw new InvalidDataException(
            $"XZTX v1 file exceeds 32-bit offsets: {fileBytes}");

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
    writer.Write((byte)'T');
    writer.Write((byte)'X');
    writer.Write(XztxVersion);
    writer.Write(
        checked((uint)first.width));
    writer.Write(
        checked((uint)first.height));
    writer.Write(
        checked((uint)first.depth));
    writer.Write(
        checked((uint)mips.Count));
    writer.Write(
        texture.SRGB
            ? FlagSrgb
            : 0u);
    writer.Write(
        checked((uint)formatBytes.Length));
    writer.Write(XztxMipRecordBytes);
    writer.Write(XztxHeaderBytes);
    writer.Write(
        checked((uint)payloadOffset));
    writer.Write(
        checked((uint)payloadBytes));
    writer.Write(formatBytes);

    for (var i = formatBytes.Length;
         i < XztxFormatNameBytes;
         ++i)
        writer.Write((byte)0);

    long nextPayload =
        payloadOffset;

    foreach (var mip in mips)
    {
        writer.Write(
            checked((uint)mip.width));
        writer.Write(
            checked((uint)mip.height));
        writer.Write(
            checked((uint)mip.depth));
        writer.Write(
            checked((uint)nextPayload));
        writer.Write(
            checked((uint)mip.data.Length));
        writer.Write(
            checked((uint)mip.sourceIndex));

        nextPayload =
            checked(
                nextPayload +
                mip.data.Length);
    }

    foreach (var mip in mips)
        writer.Write(mip.data);

    writer.Flush();

    if (stream.Length != fileBytes)
        throw new InvalidDataException(
            $"XZTX size mismatch expected={fileBytes} actual={stream.Length}");

    return (
        first.width,
        first.height,
        first.depth,
        mips.Count,
        format,
        texture.SRGB,
        payloadBytes,
        fileBytes);
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

    return normalized[(slash + 1)..];
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
