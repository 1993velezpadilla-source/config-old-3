using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Material;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEMaterialAudit <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
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

using var censusDoc = JsonDocument.Parse(
    File.ReadAllText(censusPath));

var rootElement = censusDoc.RootElement;
var censusClassCounts =
    rootElement.GetProperty("classCounts")
        .EnumerateObject()
        .ToDictionary(
            row => row.Name,
            row => row.Value.GetInt32(),
            StringComparer.Ordinal);

var materialInterfaceClassNames = new HashSet<string>(
    new[]
    {
        "Material",
        "MaterialInterface",
        "MaterialInstance",
        "MaterialInstanceConstant",
        "MaterialInstanceDynamic"
    },
    StringComparer.Ordinal);

var expectedMaterialInterfaces =
    materialInterfaceClassNames.Sum(name =>
        censusClassCounts.TryGetValue(name, out var count)
            ? count
            : 0);

var candidatePackages =
    rootElement.GetProperty("packages")
        .EnumerateArray()
        .Where(row =>
            row.GetProperty("classes")
                .EnumerateObject()
                .Any(property =>
                    property.Name.Contains(
                        "Material",
                        StringComparison.Ordinal)))
        .Select(row =>
            NormalizeMergedShardPath(
                row.GetProperty("packagePath").GetString()
                ?? throw new InvalidDataException(
                    "packagePath missing")))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(
            value => value,
            StringComparer.OrdinalIgnoreCase)
        .ToArray();

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    new VersionContainer(sourceGame),
    StringComparer.OrdinalIgnoreCase)
{
    MappingsContainer =
        new FileUsmapTypeMappingsProvider(mappingsPath)
};

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var rows = new List<object>();
var packageFailures = new List<object>();
var materialFailures = new List<object>();
var unresolvedTextureRefs = new List<object>();
var observedClassCounts = new Dictionary<string, int>(
    StringComparer.Ordinal);

var packagesLoaded = 0;
var materialExportsDecoded = 0;
var textureReferenceCount = 0;
var textureLoadCount = 0;
var scalarCount = 0;
var colorCount = 0;
var switchCount = 0;
var rawPropertyKeyCount = 0;

foreach (var logicalPackage in candidatePackages)
{
    var resolvedPath = ResolveProviderPackagePath(
        provider,
        logicalPackage);

    if (resolvedPath is null)
    {
        packageFailures.Add(new
        {
            packagePath = logicalPackage,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolvedPath);
        packagesLoaded++;

        var materials = package.GetExports()
            .OfType<UMaterialInterface>()
            .OrderBy(
                material => material.GetPathName(),
                StringComparer.Ordinal)
            .ToArray();

        foreach (var material in materials)
        {
            try
            {
                materialExportsDecoded++;

                observedClassCounts.TryGetValue(
                    material.ExportType,
                    out var previousClassCount);
                observedClassCounts[material.ExportType] =
                    previousClassCount + 1;

                var parameters = new CMaterialParams2();
                material.GetParams(
                    parameters,
                    EMaterialDepth.AllLayers);

                var textures = new List<object>();
                foreach (var textureEntry in parameters.Textures
                             .OrderBy(
                                 row => row.Key,
                                 StringComparer.Ordinal))
                {
                    textureReferenceCount++;

                    if (textureEntry.Value is UTexture texture)
                    {
                        textureLoadCount++;
                        textures.Add(new
                        {
                            parameter = textureEntry.Key,
                            objectPath = texture.GetPathName(),
                            exportType = texture.ExportType,
                            loaded = true
                        });
                    }
                    else
                    {
                        var unresolved = new
                        {
                            materialPath = material.GetPathName(),
                            parameter = textureEntry.Key,
                            reference =
                                textureEntry.Value.ToString(),
                            referenceType =
                                textureEntry.Value.GetType().FullName
                        };
                        unresolvedTextureRefs.Add(unresolved);
                        textures.Add(new
                        {
                            parameter = textureEntry.Key,
                            objectPath = (string?)null,
                            exportType = (string?)null,
                            loaded = false,
                            reference =
                                textureEntry.Value.ToString(),
                            referenceType =
                                textureEntry.Value.GetType().FullName
                        });
                    }
                }

                var scalars = parameters.Scalars
                    .OrderBy(
                        row => row.Key,
                        StringComparer.Ordinal)
                    .Select(row => new
                    {
                        name = row.Key,
                        value = row.Value
                    })
                    .ToArray();

                var colors = parameters.Colors
                    .OrderBy(
                        row => row.Key,
                        StringComparer.Ordinal)
                    .Select(row => new
                    {
                        name = row.Key,
                        r = row.Value.R,
                        g = row.Value.G,
                        b = row.Value.B,
                        a = row.Value.A
                    })
                    .ToArray();

                var switches = parameters.Switches
                    .OrderBy(
                        row => row.Key,
                        StringComparer.Ordinal)
                    .Select(row => new
                    {
                        name = row.Key,
                        value = row.Value
                    })
                    .ToArray();

                var propertyKeys = parameters.Properties.Keys
                    .OrderBy(
                        name => name,
                        StringComparer.Ordinal)
                    .ToArray();

                scalarCount += scalars.Length;
                colorCount += colors.Length;
                switchCount += switches.Length;
                rawPropertyKeyCount += propertyKeys.Length;

                rows.Add(new
                {
                    objectPath = material.GetPathName(),
                    exportType = material.ExportType,
                    packagePath = logicalPackage,
                    resolvedPackagePath = resolvedPath,
                    blendMode = parameters.BlendMode.ToString(),
                    shadingModel =
                        parameters.ShadingModel.ToString(),
                    opacityMaskClipValue =
                        material is UMaterial concreteMaterial
                            ? concreteMaterial.OpacityMaskClipValue
                            : (float?)null,
                    twoSided =
                        material is UMaterial twoSidedMaterial
                            ? twoSidedMaterial.TwoSided
                            : (bool?)null,
                    disableDepthTest =
                        material is UMaterial depthMaterial
                            ? depthMaterial.bDisableDepthTest
                            : (bool?)null,
                    isMasked =
                        material is UMaterial maskedMaterial
                            ? maskedMaterial.bIsMasked
                            : (bool?)null,
                    textureCount = textures.Count,
                    scalarCount = scalars.Length,
                    colorCount = colors.Length,
                    switchCount = switches.Length,
                    rawPropertyKeyCount = propertyKeys.Length,
                    textures,
                    scalars,
                    colors,
                    switches,
                    rawPropertyKeys = propertyKeys
                });
            }
            catch (Exception e)
            {
                materialFailures.Add(new
                {
                    packagePath = logicalPackage,
                    materialPath = material.GetPathName(),
                    exportType = material.ExportType,
                    error =
                        e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        packageFailures.Add(new
        {
            packagePath = logicalPackage,
            resolvedPath,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var classCoverageFailures = new List<object>();

foreach (var observed in observedClassCounts
             .OrderBy(
                 row => row.Key,
                 StringComparer.Ordinal))
{
    if (!censusClassCounts.TryGetValue(
            observed.Key,
            out var expected))
    {
        classCoverageFailures.Add(new
        {
            className = observed.Key,
            expected = (int?)null,
            decoded = observed.Value,
            error = "class absent from census"
        });
        continue;
    }

    if (expected != observed.Value)
    {
        classCoverageFailures.Add(new
        {
            className = observed.Key,
            expected = (int?)expected,
            decoded = observed.Value,
            error = "decoded count mismatch"
        });
    }
}

var ready =
    candidatePackages.Length > 0 &&
    packagesLoaded == candidatePackages.Length &&
    materialExportsDecoded > 0 &&
    (expectedMaterialInterfaces == 0 ||
        materialExportsDecoded == expectedMaterialInterfaces) &&
    packageFailures.Count == 0 &&
    materialFailures.Count == 0 &&
    unresolvedTextureRefs.Count == 0 &&
    classCoverageFailures.Count == 0;

var output = new
{
    schemaVersion = 1,
    format = "xziel_ue_material_audit_v1",
    sourceGameName,
    summary = new
    {
        candidatePackageCount = candidatePackages.Length,
        packagesLoaded,
        expectedMaterialInterfaces,
        materialExportsDecoded,
        materialClassCount = observedClassCounts.Count,
        textureReferenceCount,
        textureLoadCount,
        unresolvedTextureReferenceCount =
            unresolvedTextureRefs.Count,
        scalarCount,
        colorCount,
        switchCount,
        rawPropertyKeyCount,
        packageFailureCount = packageFailures.Count,
        materialFailureCount = materialFailures.Count,
        classCoverageFailureCount =
            classCoverageFailures.Count,
        ready
    },
    observedClassCounts = observedClassCounts
        .OrderBy(row => row.Key)
        .ToDictionary(row => row.Key, row => row.Value),
    classCoverageFailures,
    packageFailures,
    materialFailures,
    unresolvedTextureRefs,
    materials = rows
};

Directory.CreateDirectory(
    Path.GetDirectoryName(
        Path.GetFullPath(outputPath))!);

File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        output,
        new JsonSerializerOptions
        {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_UE_MATERIAL_AUDIT " +
    JsonSerializer.Serialize(output.summary));

foreach (var failure in classCoverageFailures.Take(30))
{
    Console.WriteLine(
        "XZIEL_UE_MATERIAL_CLASS_COVERAGE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

foreach (var failure in packageFailures.Take(30))
{
    Console.WriteLine(
        "XZIEL_UE_MATERIAL_PACKAGE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

foreach (var failure in materialFailures.Take(30))
{
    Console.WriteLine(
        "XZIEL_UE_MATERIAL_DECODE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

foreach (var failure in unresolvedTextureRefs.Take(30))
{
    Console.WriteLine(
        "XZIEL_UE_MATERIAL_TEXTURE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_MATERIAL_AUDIT_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_MATERIAL_AUDIT_GREEN");
return 0;

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

    for (var i = 0;
         i < shardNumber.Length;
         ++i)
    {
        if (!char.IsDigit(shardNumber[i]))
            return normalized;
    }

    return normalized[(slash + 1)..];
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized =
        logicalPath.Replace('\\', '/').TrimStart('/');

    if (provider.Files.ContainsKey(normalized))
        return normalized;

    return provider.Files.Keys
        .Where(key => key.EndsWith(
            normalized,
            StringComparison.OrdinalIgnoreCase))
        .OrderBy(key => key.Length)
        .ThenBy(
            key => key,
            StringComparer.OrdinalIgnoreCase)
        .FirstOrDefault();
}
