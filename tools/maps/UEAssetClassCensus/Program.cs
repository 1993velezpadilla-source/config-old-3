using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Readers;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length < 2 || args.Length > 5)
{
    Console.Error.WriteLine(
        "usage: UEAssetClassCensus <unpacked-root> <output-json> [source-game | shard-index shard-count [source-game]]");
    return 2;
}

var shardIndex = 0;
var shardCount = 1;
var sourceGameName = "ue4.21";

if (args.Length >= 3)
{
    if (int.TryParse(args[2], out shardIndex))
    {
        if (args.Length < 4 || !int.TryParse(args[3], out shardCount))
        {
            Console.Error.WriteLine("shard-count required after shard-index");
            return 2;
        }

        if (args.Length >= 5)
            sourceGameName = args[4];
    }
    else
    {
        if (args.Length != 3)
        {
            Console.Error.WriteLine(
                "source-game alone must be the only optional argument");
            return 2;
        }

        sourceGameName = args[2];
    }
}

if (shardCount <= 0 || shardIndex < 0 || shardIndex >= shardCount)
{
    Console.Error.WriteLine("invalid shard arguments");
    return 2;
}

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

var provider =
    new DefaultFileProvider(
        args[0],
        SearchOption.AllDirectories,
        true,
        new VersionContainer(sourceGame));

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var packages =
    provider.Files.Values
        .Where(f => f.IsUePackage)
        .Select(f => f.Path)
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x)
        .Where((_, index) => index % shardCount == shardIndex)
        .ToArray();

var classCounts =
    new SortedDictionary<string, int>(StringComparer.Ordinal);
var packageExtensionCounts =
    new SortedDictionary<string, int>(StringComparer.OrdinalIgnoreCase);
var packageLoadFailures =
    new List<object>();
var packageRows =
    new List<object>();

var totalExports = 0;
var packagesLoaded = 0;
var savedEngineVersionCounts =
    new SortedDictionary<string, int>(StringComparer.Ordinal);
var fileVersionCounts =
    new SortedDictionary<string, int>(StringComparer.Ordinal);

foreach (var packagePath in packages)
{
    var extension =
        Path.GetExtension(packagePath).ToLowerInvariant();

    packageExtensionCounts[extension] =
        packageExtensionCounts.GetValueOrDefault(extension) + 1;

    try
    {
        if (!provider.TryGetGameFile(packagePath, out var gameFile))
        {
            throw new InvalidOperationException(
                "provider could not resolve package file");
        }

        /*
         * Critical: do NOT use provider.LoadPackage() here. CUE4Parse's
         * LoadPackage opens the companion .uexp reader even in lazy mode.
         * For class census we only need the cooked package header tables,
         * which live in .uasset/.umap.
         */
        using var uassetReader = gameFile.CreateReader();
        /*
         * Header-only census must not let CUE4Parse resolve imports through
         * the provider. FObjectExport eagerly touches ClassIndex.Name while
         * parsing the export table; with a provider that can recursively
         * load imported packages and trigger unversioned-property
         * deserialization, which requires mappings and defeats this census.
         *
         * The reader already carries the selected UE version. Passing a null
         * provider keeps Package construction limited to this package's
         * header tables. We resolve class names from ImportMap/ExportMap
         * directly below.
         */
        var package = new Package(
            uassetReader,
            (FArchive?) null,
            (FArchive?) null,
            (FArchive?) null,
            null,
            true);

        packagesLoaded++;
        totalExports += package.ExportMap.Length;

        var savedEngine =
            package.Summary.SavedByEngineVersion?.ToString()
            ?? "<none>";
        savedEngineVersionCounts[savedEngine] =
            savedEngineVersionCounts.GetValueOrDefault(savedEngine) + 1;

        var fileVersion =
            package.Summary.FileVersionUE.ToString();
        fileVersionCounts[fileVersion] =
            fileVersionCounts.GetValueOrDefault(fileVersion) + 1;

        var localClasses =
            new SortedDictionary<string, int>(StringComparer.Ordinal);

        foreach (var export in package.ExportMap)
        {
            string type;
            var classIndex = export.ClassIndex;

            if (classIndex.IsImport)
            {
                var importIndex = -classIndex.Index - 1;
                type =
                    importIndex >= 0 &&
                    importIndex < package.ImportMap.Length
                        ? package.ImportMap[importIndex].ObjectName.Text
                        : "<invalid-import-class-index>";
            }
            else if (classIndex.IsExport)
            {
                var exportIndex = classIndex.Index - 1;
                type =
                    exportIndex >= 0 &&
                    exportIndex < package.ExportMap.Length
                        ? package.ExportMap[exportIndex].ObjectName.Text
                        : "<invalid-export-class-index>";
            }
            else
            {
                type = "<null-class>";
            }

            classCounts[type] =
                classCounts.GetValueOrDefault(type) + 1;
            localClasses[type] =
                localClasses.GetValueOrDefault(type) + 1;
        }

        packageRows.Add(new {
            packagePath,
            exportCount = package.ExportMap.Length,
            classes = localClasses
        });
    }
    catch (Exception e)
    {
        packageLoadFailures.Add(new {
            packagePath,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var report = new {
    schemaVersion = 1,
    root = Path.GetFullPath(args[0]),
    shardIndex,
    shardCount,
    sourceGame = sourceGame.ToString(),
    sourceGameName,
    packageCount = packages.Length,
    packagesLoaded,
    packageLoadFailureCount = packageLoadFailures.Count,
    totalExports,
    uniqueExportClassCount = classCounts.Count,
    savedEngineVersionCounts,
    fileVersionCounts,
    packageExtensionCounts,
    classCounts,
    packageLoadFailures,
    packages = packageRows
};

Directory.CreateDirectory(
    Path.GetDirectoryName(
        Path.GetFullPath(args[1]))!);

File.WriteAllText(
    args[1],
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_UE_ASSET_CLASS_CENSUS_OK " +
    JsonSerializer.Serialize(
        new {
            report.packageCount,
            report.packagesLoaded,
            report.packageLoadFailureCount,
            report.totalExports,
            report.uniqueExportClassCount,
            report.sourceGameName
        }));

foreach (var pair in classCounts
    .OrderByDescending(x => x.Value)
    .Take(80))
{
    Console.WriteLine(
        $"XZIEL_UE_CLASS {pair.Value} {pair.Key}");
}

foreach (var failure in packageLoadFailures.Take(20))
{
    Console.WriteLine(
        "XZIEL_UE_PACKAGE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

/*
 * A shard must always finish and emit its report. The workflow merges every
 * shard and applies the zero-failure gate globally so diagnostics are never
 * lost just because one package failed.
 */
return 0;
