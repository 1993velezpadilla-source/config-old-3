using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length < 6 || args.Length > 7)
{
    Console.Error.WriteLine(
        "usage: UEAssetPropertySweep <unpacked-root> <mappings.usmap> <class-census.json> <output-json> <shard-index> <shard-count> [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputPath = args[3];

if (!int.TryParse(args[4], out var shardIndex) ||
    !int.TryParse(args[5], out var shardCount) ||
    shardCount <= 0 ||
    shardIndex < 0 ||
    shardIndex >= shardCount)
{
    Console.Error.WriteLine("invalid shard arguments");
    return 2;
}

var sourceGameName = args.Length >= 7 ? args[6] : "ue5.1";

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" =>
            EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" =>
            EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

if (!File.Exists(mappingsPath))
    throw new FileNotFoundException("mappings file missing", mappingsPath);

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
var allRows = censusDoc.RootElement.GetProperty("packages");

var logicalPackages = allRows
    .EnumerateArray()
    .Select(row => row.GetProperty("packagePath").GetString())
    .Where(path => !string.IsNullOrWhiteSpace(path))
    .Select(path => NormalizeMergedShardPath(path!))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
    .Where((_, index) => index % shardCount == shardIndex)
    .ToArray();

var provider =
    new DefaultFileProvider(
        root,
        SearchOption.AllDirectories,
        true,
        new VersionContainer(sourceGame))
    {
        MappingsContainer =
            new FileUsmapTypeMappingsProvider(mappingsPath)
    };

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var providerIndex = BuildProviderIndex(provider);

var packageLoadFailures = new List<object>();
var exportLoadFailures = new List<object>();
var packageSuccesses = 0;
var exportSuccesses = 0;
var exportsWithProperties = 0;
var propertyTagCount = 0;
var generatedExports = 0;
var generatedExportsWithProperties = 0;

foreach (var logicalPath in logicalPackages)
{
    var resolvedPath = ResolveProviderPackagePath(
        provider,
        providerIndex,
        logicalPath);

    if (resolvedPath is null)
    {
        packageLoadFailures.Add(new
        {
            packagePath = logicalPath,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        if (!provider.TryLoadPackage(resolvedPath, out var package))
        {
            packageLoadFailures.Add(new
            {
                packagePath = logicalPath,
                resolvedPath,
                error = "provider.TryLoadPackage returned false"
            });
            continue;
        }

        packageSuccesses++;

        for (var exportIndex = 0;
             exportIndex < package.ExportMapLength;
             ++exportIndex)
        {
            try
            {
                var export = package.GetExport(exportIndex);
                if (export is null)
                    continue;

                exportSuccesses++;

                var isGenerated =
                    export.ExportType.EndsWith(
                        "_C",
                        StringComparison.Ordinal) ||
                    export.ExportType.Contains(
                        "BlueprintGeneratedClass",
                        StringComparison.Ordinal);

                if (isGenerated)
                    generatedExports++;

                if (export.Properties.Count > 0)
                {
                    exportsWithProperties++;
                    propertyTagCount += export.Properties.Count;

                    if (isGenerated)
                        generatedExportsWithProperties++;
                }
            }
            catch (Exception e)
            {
                exportLoadFailures.Add(new
                {
                    packagePath = logicalPath,
                    resolvedPath,
                    exportIndex,
                    error = e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        packageLoadFailures.Add(new
        {
            packagePath = logicalPath,
            resolvedPath,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var report = new
{
    schemaVersion = 1,
    sourceGameName,
    shardIndex,
    shardCount,
    mappingTypes = provider.MappingsForGame?.Types.Count ?? 0,
    mappingEnums = provider.MappingsForGame?.Enums.Count ?? 0,
    packageCount = logicalPackages.Length,
    packageSuccesses,
    packageLoadFailureCount = packageLoadFailures.Count,
    exportSuccesses,
    exportLoadFailureCount = exportLoadFailures.Count,
    exportsWithProperties,
    propertyTagCount,
    generatedExports,
    generatedExportsWithProperties,
    packageLoadFailures,
    exportLoadFailures
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);

File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_PROPERTY_SWEEP_SHARD " +
    JsonSerializer.Serialize(new
    {
        shardIndex,
        shardCount,
        report.packageCount,
        packageSuccesses,
        report.packageLoadFailureCount,
        exportSuccesses,
        report.exportLoadFailureCount,
        exportsWithProperties,
        propertyTagCount,
        generatedExports,
        generatedExportsWithProperties
    }));

foreach (var failure in packageLoadFailures.Take(20))
{
    Console.WriteLine(
        "XZIEL_UE_PROPERTY_PACKAGE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

foreach (var failure in exportLoadFailures.Take(40))
{
    Console.WriteLine(
        "XZIEL_UE_PROPERTY_EXPORT_FAILURE " +
        JsonSerializer.Serialize(failure));
}

/*
 * Always emit a shard report. The workflow merges all shards and applies the
 * zero-failure gate globally so one bad package cannot hide the remaining
 * incompatibilities.
 */
return 0;

static Dictionary<string, string> BuildProviderIndex(
    DefaultFileProvider provider)
{
    var index =
        new Dictionary<string, string>(
            StringComparer.OrdinalIgnoreCase);

    foreach (var key in provider.Files.Keys)
    {
        var normalized = key.Replace('\\', '/');
        index.TryAdd(normalized, key);

        var firstSlash = normalized.IndexOf('/');
        if (firstSlash >= 0 && firstSlash + 1 < normalized.Length)
        {
            index.TryAdd(
                normalized[(firstSlash + 1)..],
                key);
        }

        foreach (var marker in new[] { "/Pavlov/", "/Engine/" })
        {
            var pos = normalized.IndexOf(
                marker,
                StringComparison.OrdinalIgnoreCase);

            if (pos >= 0)
            {
                index.TryAdd(
                    normalized[(pos + 1)..],
                    key);
            }
        }
    }

    return index;
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    IReadOnlyDictionary<string, string> providerIndex,
    string logicalPath)
{
    if (provider.TryGetGameFile(logicalPath, out _))
        return logicalPath;

    var normalized = logicalPath.Replace('\\', '/');

    if (providerIndex.TryGetValue(
            normalized,
            out var exact))
        return exact;

    return provider.Files.Keys.FirstOrDefault(
        key => key.EndsWith(
            normalized,
            StringComparison.OrdinalIgnoreCase));
}

static string NormalizeMergedShardPath(string path)
{
    var normalized = path.Replace('\\', '/');

    if (!normalized.StartsWith(
            "shard-",
            StringComparison.OrdinalIgnoreCase))
        return normalized;

    var slash = normalized.IndexOf('/');
    if (slash <= 6)
        return normalized;

    var shardNumber =
        normalized.AsSpan(6, slash - 6);

    for (var i = 0; i < shardNumber.Length; ++i)
    {
        if (!char.IsDigit(shardNumber[i]))
            return normalized;
    }

    return normalized[(slash + 1)..];
}
