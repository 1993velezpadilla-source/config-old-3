using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length != 2)
{
    Console.Error.WriteLine(
        "usage: UEAssetClassCensus <unpacked-root> <output-json>");
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
        var exports =
            provider.LoadPackage(packagePath)
                .GetExports()
                .ToArray();

        packagesLoaded++;
        totalExports += exports.Length;

        var localClasses =
            new SortedDictionary<string, int>(StringComparer.Ordinal);

        foreach (var export in exports)
        {
            var type =
                export.GetType().FullName
                ?? export.GetType().Name;

            classCounts[type] =
                classCounts.GetValueOrDefault(type) + 1;
            localClasses[type] =
                localClasses.GetValueOrDefault(type) + 1;
        }

        packageRows.Add(new {
            packagePath,
            exportCount = exports.Length,
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
