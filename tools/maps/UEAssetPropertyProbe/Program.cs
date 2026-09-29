using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length < 4 || args.Length > 5)
{
    Console.Error.WriteLine(
        "usage: UEAssetPropertyProbe <unpacked-root> <mappings.usmap> <class-census.json> <output-json> [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputPath = args[3];
var sourceGameName = args.Length >= 5 ? args[4] : "ue5.1";

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
var packageRows = censusDoc.RootElement.GetProperty("packages");

var categories = new[]
{
    new ProbeCategory(
        "world_geometry",
        name => name is "StaticMeshActor" or "StaticMesh" or "Model"),
    new ProbeCategory(
        "lighting",
        name => name.Contains("Light", StringComparison.OrdinalIgnoreCase) ||
                name.Contains("Decal", StringComparison.OrdinalIgnoreCase)),
    new ProbeCategory(
        "audio",
        name => name.StartsWith("Sound", StringComparison.OrdinalIgnoreCase) ||
                name.StartsWith("Audio", StringComparison.OrdinalIgnoreCase) ||
                name is "AmbientSound"),
    new ProbeCategory(
        "animation_rig",
        name => name.StartsWith("Anim", StringComparison.OrdinalIgnoreCase) ||
                name.StartsWith("Skeletal", StringComparison.OrdinalIgnoreCase) ||
                name.StartsWith("Skeleton", StringComparison.OrdinalIgnoreCase)),
    new ProbeCategory(
        "fx",
        name => name.StartsWith("Particle", StringComparison.OrdinalIgnoreCase) ||
                name.StartsWith("Niagara", StringComparison.OrdinalIgnoreCase) ||
                name is "Emitter"),
    new ProbeCategory(
        "generated_gameplay",
        name => name.EndsWith("_C", StringComparison.Ordinal)),
    new ProbeCategory(
        "spawn_ai",
        name =>
            name.EndsWith("_C", StringComparison.Ordinal) &&
            (name.Contains("spawn", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("zombie", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("dog", StringComparison.OrdinalIgnoreCase))),
    new ProbeCategory(
        "interactables",
        name =>
            name.EndsWith("_C", StringComparison.Ordinal) &&
            (name.Contains("door", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("barricade", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("wallbuy", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("buyable", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("mystery", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("trap", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("interact", StringComparison.OrdinalIgnoreCase) ||
             name.Contains("perk", StringComparison.OrdinalIgnoreCase))),
    new ProbeCategory(
        "hud_ui",
        name =>
            name.Contains("Widget", StringComparison.OrdinalIgnoreCase) ||
            name is "TextBlock" or "TextRenderComponent" ||
            name.StartsWith("Canvas", StringComparison.OrdinalIgnoreCase))
};

var selected = new Dictionary<string, SelectedPackage>(
    StringComparer.OrdinalIgnoreCase);
var categorySelections = categories.ToDictionary(
    x => x.Name,
    _ => new List<string>(),
    StringComparer.Ordinal);

foreach (var row in packageRows.EnumerateArray())
{
    var packagePath = row.GetProperty("packagePath").GetString();
    if (string.IsNullOrWhiteSpace(packagePath))
        continue;

    packagePath = NormalizeMergedShardPath(packagePath);

    var classes = row.GetProperty("classes");
    var classNames = classes.EnumerateObject().Select(x => x.Name).ToArray();

    foreach (var category in categories)
    {
        if (categorySelections[category.Name].Count >= 2)
            continue;

        var matched = classNames.Where(category.Match).ToArray();
        if (matched.Length == 0)
            continue;

        if (!selected.TryGetValue(packagePath, out var existing))
        {
            existing = new SelectedPackage(packagePath);
            selected.Add(packagePath, existing);
        }

        existing.Categories.Add(category.Name);
        foreach (var name in matched.Take(8))
            existing.ExpectedClasses.Add(name);

        categorySelections[category.Name].Add(packagePath);
    }

    if (categorySelections.All(x => x.Value.Count >= 2))
        break;
}

var missingCategories = categorySelections
    .Where(x => x.Value.Count == 0)
    .Select(x => x.Key)
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

var rows = new List<object>();
var propertyNames = new SortedSet<string>(StringComparer.Ordinal);
var decodedCategorySet = new SortedSet<string>(StringComparer.Ordinal);

var packageSuccesses = 0;
var packageFailures = 0;
var exportSuccesses = 0;
var exportFailures = 0;
var exportsWithProperties = 0;
var propertyTagCount = 0;
var generatedExports = 0;
var generatedExportsWithProperties = 0;
var transformPropertyHits = 0;

var transformNames = new HashSet<string>(
    new[]
    {
        "RelativeLocation",
        "RelativeRotation",
        "RelativeScale3D",
        "RootComponent",
        "StaticMesh",
        "AttachParent",
        "OverrideMaterials"
    },
    StringComparer.OrdinalIgnoreCase);

foreach (var selectedPackage in selected.Values
    .OrderBy(x => x.PackagePath, StringComparer.Ordinal))
{
    var rowExportSuccesses = 0;
    var rowExportFailures = 0;
    var rowPropertyTags = 0;
    var rowExportsWithProperties = 0;
    var rowGeneratedExports = 0;
    var rowGeneratedWithProperties = 0;
    var rowTypes = new SortedSet<string>(StringComparer.Ordinal);
    var rowError = "";

    try
    {
        if (!provider.TryLoadPackage(
                selectedPackage.PackagePath,
                out var package))
        {
            throw new InvalidOperationException(
                "provider.TryLoadPackage returned false");
        }

        packageSuccesses++;

        for (var i = 0; i < package.ExportMapLength; ++i)
        {
            try
            {
                var export = package.GetExport(i);
                if (export is null)
                    continue;

                exportSuccesses++;
                rowExportSuccesses++;
                rowTypes.Add(export.ExportType);

                var isGenerated =
                    export.ExportType.EndsWith(
                        "_C",
                        StringComparison.Ordinal) ||
                    export.ExportType.Contains(
                        "BlueprintGeneratedClass",
                        StringComparison.Ordinal);

                if (isGenerated)
                {
                    generatedExports++;
                    rowGeneratedExports++;
                }

                if (export.Properties.Count > 0)
                {
                    exportsWithProperties++;
                    rowExportsWithProperties++;
                    propertyTagCount += export.Properties.Count;
                    rowPropertyTags += export.Properties.Count;

                    if (isGenerated)
                    {
                        generatedExportsWithProperties++;
                        rowGeneratedWithProperties++;
                    }

                    foreach (var property in export.Properties)
                    {
                        propertyNames.Add(property.Name.Text);
                        if (transformNames.Contains(property.Name.Text))
                            transformPropertyHits++;
                    }
                }
            }
            catch (Exception e)
            {
                exportFailures++;
                rowExportFailures++;
                if (rowError.Length == 0)
                    rowError =
                        e.GetType().FullName + ": " + e.Message;
            }
        }

        if (rowExportFailures == 0)
        {
            foreach (var category in selectedPackage.Categories)
                decodedCategorySet.Add(category);
        }
    }
    catch (Exception e)
    {
        packageFailures++;
        rowError = e.GetType().FullName + ": " + e.Message;
    }

    rows.Add(new
    {
        packagePath = selectedPackage.PackagePath,
        categories = selectedPackage.Categories.OrderBy(x => x).ToArray(),
        expectedClasses = selectedPackage.ExpectedClasses.OrderBy(x => x).ToArray(),
        exportSuccesses = rowExportSuccesses,
        exportFailures = rowExportFailures,
        exportsWithProperties = rowExportsWithProperties,
        propertyTags = rowPropertyTags,
        generatedExports = rowGeneratedExports,
        generatedExportsWithProperties = rowGeneratedWithProperties,
        exportTypes = rowTypes.ToArray(),
        error = rowError
    });
}

var mappingTypes = provider.MappingsForGame?.Types.Count ?? 0;
var mappingEnums = provider.MappingsForGame?.Enums.Count ?? 0;

var ready =
    missingCategories.Length == 0 &&
    selected.Count >= categories.Length &&
    mappingTypes > 100 &&
    packageFailures == 0 &&
    exportFailures == 0 &&
    exportSuccesses > 0 &&
    exportsWithProperties > 0 &&
    propertyTagCount > 0 &&
    generatedExports > 0 &&
    generatedExportsWithProperties > 0 &&
    transformPropertyHits > 0 &&
    decodedCategorySet.Count == categories.Length;

var report = new
{
    schemaVersion = 1,
    sourceGameName,
    mappingsPath = Path.GetFullPath(mappingsPath),
    mappingTypes,
    mappingEnums,
    requestedCategories = categories.Select(x => x.Name).ToArray(),
    missingCategories,
    selectedPackageCount = selected.Count,
    packageSuccesses,
    packageFailures,
    exportSuccesses,
    exportFailures,
    exportsWithProperties,
    propertyTagCount,
    generatedExports,
    generatedExportsWithProperties,
    transformPropertyHits,
    decodedCategories = decodedCategorySet.ToArray(),
    propertyNameSamples = propertyNames.Take(250).ToArray(),
    packages = rows,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_PROPERTY_PROBE " +
    JsonSerializer.Serialize(new
    {
        mappingTypes,
        mappingEnums,
        selectedPackages = selected.Count,
        packageFailures,
        exportSuccesses,
        exportFailures,
        exportsWithProperties,
        propertyTagCount,
        generatedExports,
        generatedExportsWithProperties,
        transformPropertyHits,
        decodedCategories = decodedCategorySet.Count,
        ready
    }));

if (!ready)
{
    foreach (var row in rows.Where(x => true).Take(50))
        Console.WriteLine(
            "XZIEL_UE_PROPERTY_PROBE_ROW " +
            JsonSerializer.Serialize(row));

    Console.WriteLine("XZIEL_UE_PROPERTY_PROBE_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_PROPERTY_PROBE_GREEN");
return 0;

sealed record ProbeCategory(
    string Name,
    Func<string, bool> Match);

sealed class SelectedPackage
{
    public string PackagePath { get; }
    public HashSet<string> Categories { get; } =
        new(StringComparer.Ordinal);
    public HashSet<string> ExpectedClasses { get; } =
        new(StringComparer.Ordinal);

    public SelectedPackage(string packagePath)
    {
        PackagePath = packagePath;
    }
}


static string NormalizeMergedShardPath(string path)
{
    /*
     * Kino class census is intentionally sharded for CI memory/runtime.
     * Each shard is mounted from its own temporary root, so shard reports
     * carry a synthetic "shard-N/" prefix. The merged census must not leak
     * that CI transport prefix into source-package identity.
     */
    var normalized = path.Replace('\\', '/');
    if (!normalized.StartsWith("shard-", StringComparison.OrdinalIgnoreCase))
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
