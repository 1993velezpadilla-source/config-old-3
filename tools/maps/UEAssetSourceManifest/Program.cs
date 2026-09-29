using System.Text;
using System.Text.Json;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;

if (args.Length < 7 || args.Length > 8)
{
    Console.Error.WriteLine(
        "usage: UEAssetSourceManifest <unpacked-root> <mappings.usmap> <class-requirements.json> <class-census.json> <output-json> <shard-index> <shard-count> [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var requirementsPath = args[2];
var censusPath = args[3];
var outputPath = args[4];

if (!int.TryParse(args[5], out var shardIndex) ||
    !int.TryParse(args[6], out var shardCount) ||
    shardCount <= 0 ||
    shardIndex < 0 ||
    shardIndex >= shardCount)
{
    Console.Error.WriteLine("invalid shard arguments");
    return 2;
}

var sourceGameName = args.Length >= 8 ? args[7] : "ue5.1";

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

using var requirementsDoc =
    JsonDocument.Parse(File.ReadAllText(requirementsPath));

var classToKind =
    requirementsDoc.RootElement
        .GetProperty("coverage")
        .EnumerateArray()
        .ToDictionary(
            row => row.GetProperty("class").GetString()
                ?? throw new InvalidDataException("class missing"),
            row => row.GetProperty("category").GetString()
                ?? throw new InvalidDataException("category missing"),
            StringComparer.Ordinal);

var expectedKindCounts =
    requirementsDoc.RootElement
        .GetProperty("categoryExportCounts")
        .EnumerateObject()
        .ToDictionary(
            p => p.Name,
            p => p.Value.GetInt64(),
            StringComparer.Ordinal);

using var censusDoc =
    JsonDocument.Parse(File.ReadAllText(censusPath));

var censusPackages =
    censusDoc.RootElement
        .GetProperty("packages")
        .EnumerateArray()
        .Select(row => new
        {
            Path = NormalizeMergedShardPath(
                row.GetProperty("packagePath").GetString()
                ?? throw new InvalidDataException("packagePath missing")),
            ExportCount = row.GetProperty("exportCount").GetInt32()
        })
        .ToArray();

var duplicates = censusPackages
    .GroupBy(x => x.Path, StringComparer.OrdinalIgnoreCase)
    .Where(g => g.Count() != 1)
    .Select(g => g.Key)
    .Take(20)
    .ToArray();

if (duplicates.Length != 0)
    throw new InvalidDataException(
        "duplicate package paths: " + string.Join(", ", duplicates));

var expectedExports = censusPackages.ToDictionary(
    x => x.Path,
    x => x.ExportCount,
    StringComparer.OrdinalIgnoreCase);

var logicalPackages = censusPackages
    .OrderBy(x => x.Path, StringComparer.OrdinalIgnoreCase)
    .Where((_, i) => i % shardCount == shardIndex)
    .ToArray();

var provider =
    new DefaultFileProvider(
        root,
        SearchOption.AllDirectories,
        true,
        new VersionContainer(sourceGame))
    {
        MappingsContainer =
            new FileUsmapTypeMappingsProvider(mappingsPath),
        UseLazyPackageSerialization = false
    };

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var providerIndex = BuildProviderIndex(provider);

var nodes = new List<object>();
var packageFailures = new List<object>();
var exportFailures = new List<object>();
var unclassified = new List<object>();
var invalidDependencies = new List<object>();
var kindCounts =
    new SortedDictionary<string, long>(StringComparer.Ordinal);
var keys = new HashSet<string>(StringComparer.Ordinal);

long packagesLoaded = 0;
long exportsDecoded = 0;
long propertyTags = 0;
long structuralEdges = 0;
long dependsMapEdges = 0;
long preloadEdges = 0;
long localDependencyEdges = 0;
long externalImportEdges = 0;
long scriptImportEdges = 0;

foreach (var censusPackage in logicalPackages)
{
    var logicalPath = censusPackage.Path;
    var resolvedPath = ResolveProviderPackagePath(
        provider,
        providerIndex,
        logicalPath);

    if (resolvedPath is null)
    {
        packageFailures.Add(new
        {
            packagePath = logicalPath,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var loaded = provider.LoadPackage(resolvedPath);

        if (loaded is not Package package)
        {
            throw new InvalidDataException(
                "expected legacy Package for uasset/umap source");
        }

        if (package.ExportMapLength != censusPackage.ExportCount)
        {
            throw new InvalidDataException(
                $"export count mismatch: census={censusPackage.ExportCount} manifest={package.ExportMapLength}");
        }

        packagesLoaded++;

        for (var exportIndex = 0;
             exportIndex < package.ExportMapLength;
             ++exportIndex)
        {
            try
            {
                var obj = package.GetExport(exportIndex);
                if (obj is null)
                    throw new InvalidDataException("null export");

                exportsDecoded++;
                propertyTags += obj.Properties.Count;

                if (!classToKind.TryGetValue(
                        obj.ExportType,
                        out var sourceKind))
                {
                    unclassified.Add(new
                    {
                        packagePath = logicalPath,
                        exportIndex,
                        className = obj.ExportType
                    });
                    continue;
                }

                kindCounts[sourceKind] =
                    kindCounts.GetValueOrDefault(sourceKind) + 1;

                var exportMeta = package.ExportMap[exportIndex];
                var localDeps = new SortedSet<int>();
                var externalDeps =
                    new SortedSet<string>(StringComparer.Ordinal);

                AddDependency(
                    package,
                    logicalPath,
                    exportIndex,
                    "class",
                    exportMeta.ClassIndex,
                    localDeps,
                    externalDeps,
                    invalidDependencies,
                    ref structuralEdges,
                    ref localDependencyEdges,
                    ref externalImportEdges,
                    ref scriptImportEdges);

                AddDependency(
                    package,
                    logicalPath,
                    exportIndex,
                    "super",
                    exportMeta.SuperIndex,
                    localDeps,
                    externalDeps,
                    invalidDependencies,
                    ref structuralEdges,
                    ref localDependencyEdges,
                    ref externalImportEdges,
                    ref scriptImportEdges);

                AddDependency(
                    package,
                    logicalPath,
                    exportIndex,
                    "template",
                    exportMeta.TemplateIndex,
                    localDeps,
                    externalDeps,
                    invalidDependencies,
                    ref structuralEdges,
                    ref localDependencyEdges,
                    ref externalImportEdges,
                    ref scriptImportEdges);

                AddDependency(
                    package,
                    logicalPath,
                    exportIndex,
                    "outer",
                    exportMeta.OuterIndex,
                    localDeps,
                    externalDeps,
                    invalidDependencies,
                    ref structuralEdges,
                    ref localDependencyEdges,
                    ref externalImportEdges,
                    ref scriptImportEdges);

                if (package.DependsMap is { } depends &&
                    exportIndex < depends.Length)
                {
                    foreach (var dependency in depends[exportIndex])
                    {
                        AddDependency(
                            package,
                            logicalPath,
                            exportIndex,
                            "depends",
                            dependency,
                            localDeps,
                            externalDeps,
                            invalidDependencies,
                            ref dependsMapEdges,
                            ref localDependencyEdges,
                            ref externalImportEdges,
                            ref scriptImportEdges);
                    }
                }

                var preloadDeclared =
                    exportMeta.SerializationBeforeSerializationDependencies +
                    exportMeta.CreateBeforeSerializationDependencies +
                    exportMeta.SerializationBeforeCreateDependencies +
                    exportMeta.CreateBeforeCreateDependencies;

                if (preloadDeclared > 0)
                {
                    if (package.PreloadDependencies is null ||
                        exportMeta.FirstExportDependency < 0 ||
                        exportMeta.FirstExportDependency + preloadDeclared >
                            package.PreloadDependencies.Length)
                    {
                        invalidDependencies.Add(new
                        {
                            packagePath = logicalPath,
                            exportIndex,
                            reason = "preload dependency range invalid",
                            first = exportMeta.FirstExportDependency,
                            count = preloadDeclared,
                            available = package.PreloadDependencies?.Length ?? 0
                        });
                    }
                    else
                    {
                        for (var i = 0; i < preloadDeclared; ++i)
                        {
                            var dependency =
                                package.PreloadDependencies[
                                    exportMeta.FirstExportDependency + i];

                            AddDependency(
                                package,
                                logicalPath,
                                exportIndex,
                                "preload",
                                dependency,
                                localDeps,
                                externalDeps,
                                invalidDependencies,
                                ref preloadEdges,
                                ref localDependencyEdges,
                                ref externalImportEdges,
                                ref scriptImportEdges);
                        }
                    }
                }

                var contentKey =
                    Fnv1a64(
                        logicalPath.ToLowerInvariant() +
                        "#" +
                        exportIndex.ToString(
                            System.Globalization.CultureInfo.InvariantCulture))
                    .ToString("x16");

                if (!keys.Add(contentKey))
                {
                    throw new InvalidDataException(
                        "duplicate content key in manifest shard: " +
                        contentKey);
                }

                nodes.Add(new
                {
                    contentKey,
                    packagePath = logicalPath,
                    exportIndex,
                    objectName = obj.Name,
                    className = obj.ExportType,
                    sourceKind,
                    propertyCount = obj.Properties.Count,
                    serialSize = exportMeta.SerialSize,
                    localExportDependencies = localDeps.ToArray(),
                    externalImports = externalDeps.ToArray(),
                    preload = new
                    {
                        exportMeta.FirstExportDependency,
                        exportMeta.SerializationBeforeSerializationDependencies,
                        exportMeta.CreateBeforeSerializationDependencies,
                        exportMeta.SerializationBeforeCreateDependencies,
                        exportMeta.CreateBeforeCreateDependencies
                    }
                });
            }
            catch (Exception e)
            {
                exportFailures.Add(new
                {
                    packagePath = logicalPath,
                    exportIndex,
                    error = e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        packageFailures.Add(new
        {
            packagePath = logicalPath,
            resolvedPath,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var expectedShardExports =
    logicalPackages.Sum(x => (long)x.ExportCount);

var ready =
    packageFailures.Count == 0 &&
    exportFailures.Count == 0 &&
    unclassified.Count == 0 &&
    invalidDependencies.Count == 0 &&
    packagesLoaded == logicalPackages.Length &&
    exportsDecoded == expectedShardExports &&
    nodes.Count == expectedShardExports;

var report = new
{
    schemaVersion = 1,
    sourceGameName,
    shardIndex,
    shardCount,
    packageCount = logicalPackages.Length,
    packagesLoaded,
    expectedExports = expectedShardExports,
    exportsDecoded,
    nodeCount = nodes.Count,
    propertyTags,
    structuralEdges,
    dependsMapEdges,
    preloadEdges,
    localDependencyEdges,
    externalImportEdges,
    scriptImportEdges,
    uniqueContentKeyCount = keys.Count,
    kindCounts,
    expectedGlobalKindCounts = expectedKindCounts,
    packageFailureCount = packageFailures.Count,
    exportFailureCount = exportFailures.Count,
    unclassifiedCount = unclassified.Count,
    invalidDependencyCount = invalidDependencies.Count,
    packageFailures,
    exportFailures,
    unclassified,
    invalidDependencies,
    nodes,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);

File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(report));

Console.WriteLine(
    "XZIEL_UE_SOURCE_MANIFEST_SHARD " +
    JsonSerializer.Serialize(new
    {
        shardIndex,
        shardCount,
        report.packageCount,
        packagesLoaded,
        expectedExports = expectedShardExports,
        exportsDecoded,
        nodeCount = nodes.Count,
        propertyTags,
        structuralEdges,
        dependsMapEdges,
        preloadEdges,
        localDependencyEdges,
        externalImportEdges,
        scriptImportEdges,
        report.packageFailureCount,
        report.exportFailureCount,
        report.unclassifiedCount,
        report.invalidDependencyCount,
        ready
    }));

foreach (var failure in packageFailures.Take(20))
    Console.WriteLine(
        "XZIEL_SOURCE_MANIFEST_PACKAGE_FAILURE " +
        JsonSerializer.Serialize(failure));

foreach (var failure in exportFailures.Take(40))
    Console.WriteLine(
        "XZIEL_SOURCE_MANIFEST_EXPORT_FAILURE " +
        JsonSerializer.Serialize(failure));

foreach (var failure in invalidDependencies.Take(40))
    Console.WriteLine(
        "XZIEL_SOURCE_MANIFEST_DEPENDENCY_FAILURE " +
        JsonSerializer.Serialize(failure));

return ready ? 0 : 5;

static void AddDependency(
    Package package,
    string packagePath,
    int exportIndex,
    string reason,
    FPackageIndex? dependency,
    SortedSet<int> localDeps,
    SortedSet<string> externalDeps,
    List<object> invalidDependencies,
    ref long sourceEdgeCounter,
    ref long localEdgeCounter,
    ref long externalEdgeCounter,
    ref long scriptEdgeCounter)
{
    if (dependency is null || dependency.IsNull)
        return;

    sourceEdgeCounter++;

    if (dependency.IsExport)
    {
        var index = dependency.Index - 1;
        if (index < 0 || index >= package.ExportMap.Length)
        {
            invalidDependencies.Add(new
            {
                packagePath,
                exportIndex,
                reason,
                dependencyIndex = dependency.Index,
                error = "export dependency out of range"
            });
            return;
        }

        localDeps.Add(index);
        localEdgeCounter++;
        return;
    }

    if (dependency.IsImport)
    {
        var index = -dependency.Index - 1;
        if (index < 0 || index >= package.ImportMap.Length)
        {
            invalidDependencies.Add(new
            {
                packagePath,
                exportIndex,
                reason,
                dependencyIndex = dependency.Index,
                error = "import dependency out of range"
            });
            return;
        }

        var import = package.ImportMap[index];
        var rootPackage = FindImportRootPackage(package, index);
        var token =
            rootPackage +
            "|" +
            import.ObjectName.Text +
            "|" +
            import.ClassName.Text;

        externalDeps.Add(token);
        externalEdgeCounter++;

        if (rootPackage.StartsWith(
                "/Script/",
                StringComparison.OrdinalIgnoreCase))
            scriptEdgeCounter++;

        return;
    }

    invalidDependencies.Add(new
    {
        packagePath,
        exportIndex,
        reason,
        dependencyIndex = dependency.Index,
        error = "dependency is neither import nor export"
    });
}

static string FindImportRootPackage(
    Package package,
    int importIndex)
{
    var currentIndex = importIndex;
    var guard = 0;

    while (currentIndex >= 0 &&
           currentIndex < package.ImportMap.Length &&
           guard++ <= package.ImportMap.Length)
    {
        var import = package.ImportMap[currentIndex];

        if (import.OuterIndex is null ||
            import.OuterIndex.IsNull)
        {
            var packageName = import.PackageName.Text;
            if (!string.IsNullOrWhiteSpace(packageName) &&
                !string.Equals(
                    packageName,
                    "None",
                    StringComparison.OrdinalIgnoreCase))
                return packageName;

            return import.ObjectName.Text;
        }

        if (import.OuterIndex.IsExport)
            return package.Name;

        if (!import.OuterIndex.IsImport)
            break;

        currentIndex = -import.OuterIndex.Index - 1;
    }

    return "<invalid-import-root>";
}

static ulong Fnv1a64(string value)
{
    const ulong offset = 14695981039346656037UL;
    const ulong prime = 1099511628211UL;

    var hash = offset;
    foreach (var b in Encoding.UTF8.GetBytes(value))
    {
        hash ^= b;
        hash *= prime;
    }

    return hash;
}

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
            index.TryAdd(
                normalized[(firstSlash + 1)..],
                key);

        foreach (var marker in new[] { "/Pavlov/", "/Engine/" })
        {
            var pos = normalized.IndexOf(
                marker,
                StringComparison.OrdinalIgnoreCase);
            if (pos >= 0)
                index.TryAdd(
                    normalized[(pos + 1)..],
                    key);
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

    if (providerIndex.TryGetValue(normalized, out var exact))
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

    var shardNumber = normalized.AsSpan(6, slash - 6);
    for (var i = 0; i < shardNumber.Length; ++i)
    {
        if (!char.IsDigit(shardNumber[i]))
            return normalized;
    }

    return normalized[(slash + 1)..];
}
