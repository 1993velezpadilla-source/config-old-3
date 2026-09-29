using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Sound;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Sounds;
using System.Text;
using System.Text.Json;

const uint XzawVersion = 1;
const uint XzawHeaderBytes = 96;
const uint XzawFormatNameBytes = 64;
const uint FlagSourceStreaming = 1u << 0;

if (args.Length is < 4 or > 6)
{
    Console.Error.WriteLine(
        "usage: UEAudioXZAW <unpacked-root> <mappings.usmap> <class-census.json> <output-dir> [max-waves] [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputDir = args[3];
var maxWaves =
    args.Length >= 5
        ? int.Parse(args[4])
        : 8;
var sourceGameName =
    args.Length >= 6
        ? args[5]
        : "ue5.1";

if (maxWaves <= 0)
    throw new ArgumentOutOfRangeException(nameof(maxWaves));

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
                    "SoundWave",
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
var formats =
    new SortedDictionary<string, int>(
        StringComparer.OrdinalIgnoreCase);

var converted = 0;
long totalPayloadBytes = 0;
long totalFileBytes = 0;

foreach (var logicalPackage in candidatePackages)
{
    if (converted >= maxWaves)
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

        var waves =
            package.GetExports()
                .OfType<USoundWave>()
                .OrderBy(
                    wave => wave.Name,
                    StringComparer.Ordinal)
                .ToArray();

        foreach (var wave in waves)
        {
            if (converted >= maxWaves)
                break;

            try
            {
                var fileName =
                    $"a{converted:D5}.xaw";
                var outPath =
                    Path.Combine(
                        outputDir,
                        fileName);

                var result =
                    WriteXzaw(
                        outPath,
                        wave);

                rows.Add(new {
                    index = converted,
                    file = fileName,
                    packagePath = logicalPackage,
                    resolvedPackagePath =
                        resolvedPath,
                    objectPath =
                        wave.GetPathName(),
                    result.format,
                    result.streaming,
                    result.payloadBytes,
                    result.fileBytes
                });

                converted++;
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
                        wave.GetPathName(),
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
    converted == maxWaves &&
    rows.Count == maxWaves &&
    failures.Count == 0 &&
    totalPayloadBytes > 0 &&
    totalFileBytes > totalPayloadBytes;

var report = new {
    schemaVersion = 1,
    format = "xziel_audio_xzaw_v1",
    sourceGameName,
    requestedSoundWaves = maxWaves,
    convertedSoundWaves = converted,
    totalPayloadBytes,
    totalFileBytes,
    formatCounts = formats,
    failureCount = failures.Count,
    soundWaves = rows,
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
    "XZIEL_UE_XZAW_PROBE " +
    JsonSerializer.Serialize(new {
        requested = maxWaves,
        converted,
        totalPayloadBytes,
        totalFileBytes,
        formats,
        failures = failures.Count,
        ready
    }));

foreach (var failure in failures.Take(50))
{
    Console.WriteLine(
        "XZIEL_UE_XZAW_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_XZAW_PROBE_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_XZAW_PROBE_GREEN");
return 0;

static (
    string format,
    bool streaming,
    long payloadBytes,
    long fileBytes
) WriteXzaw(
    string outputPath,
    USoundWave wave)
{
    wave.Decode(
        shouldDecompress: false,
        out var audioFormat,
        out var data);

    if (string.IsNullOrWhiteSpace(
            audioFormat))
        throw new InvalidDataException(
            "sound wave format unresolved");

    if (data is null ||
        data.Length == 0)
        throw new InvalidDataException(
            "sound wave has no compressed payload");

    var formatBytes =
        Encoding.ASCII.GetBytes(
            audioFormat);

    if (formatBytes.Length == 0 ||
        formatBytes.Length >=
            XzawFormatNameBytes)
        throw new InvalidDataException(
            $"XZAW format name too long: {audioFormat}");

    long fileBytes =
        checked(
            (long)XzawHeaderBytes +
            data.LongLength);

    if (fileBytes > uint.MaxValue)
        throw new InvalidDataException(
            $"XZAW v1 file exceeds 32-bit offsets: {fileBytes}");

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
    writer.Write((byte)'W');
    writer.Write(XzawVersion);
    writer.Write(
        wave.bStreaming
            ? FlagSourceStreaming
            : 0u);
    writer.Write(
        checked((uint)formatBytes.Length));
    writer.Write(XzawHeaderBytes);
    writer.Write(XzawHeaderBytes);
    writer.Write(
        checked((uint)data.Length));
    writer.Write(0u);
    writer.Write(formatBytes);

    for (var i = formatBytes.Length;
         i < XzawFormatNameBytes;
         ++i)
        writer.Write((byte)0);

    writer.Write(data);
    writer.Flush();

    if (stream.Length != fileBytes)
        throw new InvalidDataException(
            $"XZAW size mismatch expected={fileBytes} actual={stream.Length}");

    return (
        audioFormat,
        wave.bStreaming,
        data.LongLength,
        stream.Length);
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
