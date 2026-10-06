using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEParticleSceneExtract <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputPath = args[3];
var sourceGameName = args[4];

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

string NormalizeMergedShardPath(string value)
{
    var path = value.Replace('\\', '/');
    return Regex.Replace(
        path,
        @"^shard-\d+/",
        "",
        RegexOptions.IgnoreCase);
}

string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized = NormalizeMergedShardPath(logicalPath);
    foreach (var file in provider.Files.Values)
    {
        var candidate = file.Path.Replace('\\', '/');
        if (candidate.Equals(normalized, StringComparison.OrdinalIgnoreCase) ||
            candidate.EndsWith("/" + normalized, StringComparison.OrdinalIgnoreCase))
            return file.Path;
    }
    return null;
}

string? ReferencePath(FPackageIndex index)
{
    if (index.IsNull)
        return null;
    return index.ResolvedObject?.GetPathName() ?? index.Name;
}

List<object> BuildHierarchy(USceneComponent start)
{
    var rows = new List<object>();
    var seen = new HashSet<string>(StringComparer.Ordinal);
    USceneComponent? current = start;

    for (var depth = 0; current is not null && depth < 64; ++depth)
    {
        var path = current.GetPathName();
        if (!seen.Add(path))
            throw new InvalidOperationException("particle component attachment cycle: " + path);

        var location = current.GetRelativeLocation();
        var rotation = current.GetRelativeRotation();
        var scale = current.GetRelativeScale3D();

        rows.Add(new
        {
            depth,
            objectPath = path,
            componentName = current.Name,
            locationUEcm = new { X = location.X, Y = location.Y, Z = location.Z },
            rotationUE = new { Pitch = rotation.Pitch, Yaw = rotation.Yaw, Roll = rotation.Roll },
            scale = new { X = scale.X, Y = scale.Y, Z = scale.Z }
        });

        current = current.GetAttachParent();
    }

    if (rows.Count == 0)
        throw new InvalidOperationException("empty particle hierarchy");

    return rows;
}

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
var mapPackages = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Select(row =>
        NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("packagePath missing")))
    .Where(path => path.EndsWith(".umap", StringComparison.OrdinalIgnoreCase))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
    .ToArray();

if (mapPackages.Length == 0)
    throw new InvalidDataException("no .umap packages in source census");

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    new VersionContainer(sourceGame),
    StringComparer.OrdinalIgnoreCase)
{
    MappingsContainer = new FileUsmapTypeMappingsProvider(mappingsPath)
};

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var rows = new List<object>();
var packageFailures = new List<object>();
var packagesLoaded = 0;
var referencedTemplateCount = 0;
var loadedTemplateCount = 0;
var nullTemplateCount = 0;
var templateTypeCounts = new SortedDictionary<string, int>(StringComparer.Ordinal);

foreach (var logicalPackage in mapPackages)
{
    var resolved = ResolveProviderPackagePath(provider, logicalPackage);
    if (resolved is null)
    {
        packageFailures.Add(new { packagePath = logicalPackage, error = "provider path unresolved" });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        foreach (var component in package.GetExports()
                     .OfType<UParticleSystemComponent>()
                     .OrderBy(x => x.GetPathName(), StringComparer.Ordinal))
        {
            var templateIndex = component.GetOrDefault<FPackageIndex>("Template");
            string? templatePath = null;
            string? templateType = null;
            var templateLoaded = false;

            if (!templateIndex.IsNull)
            {
                referencedTemplateCount++;
                templatePath = ReferencePath(templateIndex);
                try
                {
                    var loaded = templateIndex.Load<UParticleSystem>();
                    if (loaded is not null)
                    {
                        templateLoaded = true;
                        loadedTemplateCount++;
                        templatePath = loaded.GetPathName();
                        templateType = loaded.ExportType;
                    }
                }
                catch
                {
                    // Preserve the exact FPackageIndex reference even when loading
                    // fails because cooked virtual namespaces do not mount it.
                }
            }
            else
            {
                nullTemplateCount++;
            }

            var typeKey =
                !string.IsNullOrWhiteSpace(templateType)
                    ? templateType!
                    : templatePath is null
                        ? "null"
                        : "unloaded_reference";
            templateTypeCounts[typeKey] =
                templateTypeCounts.GetValueOrDefault(typeKey) + 1;

            var componentPath = component.GetPathName();
            var lastDot = componentPath.LastIndexOf('.');
            var parentPath = lastDot > 0 ? componentPath[..lastDot] : "";
            var parentName =
                parentPath.Length > 0
                    ? parentPath.Split('.').Last()
                    : "";

            var explicitVisible =
                component.GetOrDefault<bool?>("bVisible");
            var hiddenInGame =
                component.GetOrDefault<bool?>("bHiddenInGame");
            var effectiveVisible =
                explicitVisible ??
                (hiddenInGame is not null
                    ? !hiddenInGame.Value
                    : true);

            rows.Add(new
            {
                id = $"particle_{rows.Count:0000}",
                packagePath = logicalPackage,
                actorName = parentName,
                componentName = component.Name,
                sourcePath = componentPath,
                hierarchy = BuildHierarchy(component),
                template = new
                {
                    objectPath = templatePath,
                    exportType = templateType,
                    loaded = templateLoaded,
                    reference = templateIndex.IsNull ? null : templateIndex.ToString()
                },
                properties = new
                {
                    autoActivate = component.GetOrDefault<bool>("bAutoActivate", true),
                    effectiveVisible,
                    hiddenInGame = hiddenInGame ?? false,
                    secondsBeforeInactive =
                        component.GetOrDefault<float>("SecondsBeforeInactive", 1.0f),
                    customTimeDilation =
                        component.GetOrDefault<float>("CustomTimeDilation", 1.0f),
                    warmupTime =
                        component.GetOrDefault<float>("WarmupTime", 0.0f),
                    warmupTickRate =
                        component.GetOrDefault<float>("WarmupTickRate", 0.0f),
                    allowRecycling =
                        component.GetOrDefault<bool>("bAllowRecycling", false),
                    resetOnDetach =
                        component.GetOrDefault<bool>("bResetOnDetach", false),
                    skipUpdateDynamicDataDuringTick =
                        component.GetOrDefault<bool>("bSkipUpdateDynamicDataDuringTick", false)
                }
            });
        }
    }
    catch (Exception ex)
    {
        packageFailures.Add(new
        {
            packagePath = logicalPackage,
            error = ex.GetType().Name + ": " + ex.Message
        });
    }
}

var ready =
    packagesLoaded == mapPackages.Length &&
    packageFailures.Count == 0 &&
    rows.Count > 0 &&
    referencedTemplateCount > 0;

var output = new
{
    schemaVersion = 1,
    sourceGame = sourceGameName,
    coordinateSystem = new
    {
        source = "Unreal Engine centimeters",
        target = "XZIEL meters X,-Y,Z",
        hierarchyConvention = "component local transforms ordered child-to-parent"
    },
    mapPackageCount = mapPackages.Length,
    packagesLoaded,
    particleComponentCount = rows.Count,
    referencedTemplateCount,
    loadedTemplateCount,
    nullTemplateCount,
    templateTypeCounts,
    particleComponents = rows,
    packageFailures,
    ready
};

Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(output, new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_PARTICLE_SCENE_EXTRACT " +
    JsonSerializer.Serialize(new
    {
        output.mapPackageCount,
        output.packagesLoaded,
        output.particleComponentCount,
        output.referencedTemplateCount,
        output.loadedTemplateCount,
        output.nullTemplateCount,
        output.templateTypeCounts,
        failureCount = packageFailures.Count,
        output.ready
    }));

if (!ready)
{
    Console.WriteLine("XZIEL_UE_PARTICLE_SCENE_EXTRACT_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_PARTICLE_SCENE_EXTRACT_GREEN");
return 0;
