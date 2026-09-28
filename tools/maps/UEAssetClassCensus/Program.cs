using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length < 2 || args.Length > 4)
{
    Console.Error.WriteLine(
        "usage: UEAssetClassCensus <unpacked-root> <output-json> [shard-index] [shard-count]");
    return 2;
}

var shardIndex = args.Length >= 3 ? int.Parse(args[2]) : 0;
var shardCount = args.Length >= 4 ? int.Parse(args[3]) : 1;

if (shardCount <= 0 || shardIndex < 0 || shardIndex >= shardCount)
{
    Console.Error.WriteLine("invalid shard arguments");
    return 2;
}

var provider =
    new DefaultFileProvider(
        args[0],
        SearchOption.AllDirectories,
        true,
        new VersionContainer(EGame.GAME_UE4_21));

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

foreach (var packagePath in packages)
{
    var extension =
        Path.GetExtension(packagePath).ToLowerInvariant();

    packageExtensionCounts[extension] =
        packageExtensionCounts.GetValueOrDefault(extension) + 1;

    try
    {
        if (!provider.TryLoadPackage(packagePath, out var package) ||
            package is not AbstractUePackage uePackage)
        {
            throw new InvalidOperationException(
                "provider could not load package metadata");
        }

        packagesLoaded++;
        totalExports += package.ExportMapLength;

        var localClasses =
            new SortedDictionary<string, int>(StringComparer.Ordinal);

        /*
         * Do not call GetExports() here. The official CUE4Parse exporter
         * demonstrates this metadata-only path specifically to inspect export
         * types without deserializing heavy texture/mesh/sound payloads.
         */
        for (var exportIndex = 0;
             exportIndex < package.ExportMapLength;
             ++exportIndex)
        {
            var pointer =
                new FPackageIndex(package, exportIndex + 1)
                    .ResolvedObject;

            if (pointer?.Class is null)
                continue;

            var dummy =
                uePackage.ConstructObject(
                    pointer.Class,
                    package);

            var type =
                dummy.GetType().FullName
                ?? dummy.GetType().Name;

            classCounts[type] =
                classCounts.GetValueOrDefault(type) + 1;
            localClasses[type] =
                localClasses.GetValueOrDefault(type) + 1;
        }

        packageRows.Add(new {
            packagePath,
            exportCount = package.ExportMapLength,
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
    packageCount = packages.Length,
    packagesLoaded,
    packageLoadFailureCount = packageLoadFailures.Count,
    totalExports,
    uniqueExportClassCount = classCounts.Count,
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
            report.uniqueExportClassCount
        }));

foreach (var pair in classCounts
    .OrderByDescending(x => x.Value)
    .Take(80))
{
    Console.WriteLine(
        $"XZIEL_UE_CLASS {pair.Value} {pair.Key}");
}

return packageLoadFailures.Count == 0 ? 0 : 5;
