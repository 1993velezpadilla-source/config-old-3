using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Material;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Objects.UObject;
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
var semanticResolutionFailures = new List<object>();
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

                var semantics =
                    ResolveMaterialSemantics(
                        material,
                        provider);

                var rawParentProperty =
                    material.Properties.FirstOrDefault(
                        p => p.Name.Text.Equals(
                            "Parent",
                            StringComparison.Ordinal));
                var rawParent =
                    rawParentProperty?.Tag?.GenericValue;

                if (!semantics.resolved)
                {
                    semanticResolutionFailures.Add(new
                    {
                        packagePath = logicalPackage,
                        materialPath = material.GetPathName(),
                        exportType = material.ExportType,
                        parentRuntimeType =
                            material is UMaterialInstance mi &&
                            mi.Parent is not null
                                ? mi.Parent.GetType().FullName
                                : null,
                        parentPath =
                            material is UMaterialInstance mi2 &&
                            mi2.Parent is not null
                                ? mi2.Parent.GetPathName()
                                : null,
                        rawParentType =
                            rawParent?.GetType().FullName,
                        rawParentValue =
                            rawParent?.ToString(),
                        rawBasePropertyOverrides =
                            material is UMaterialInstance
                                ? parameters.Properties
                                    .Where(x =>
                                        x.Key.Contains(
                                            "Override",
                                            StringComparison.OrdinalIgnoreCase) ||
                                        x.Key.Contains(
                                            "BaseProperty",
                                            StringComparison.OrdinalIgnoreCase))
                                    .OrderBy(x => x.Key)
                                    .ToDictionary(
                                        x => x.Key,
                                        x => x.Value?.ToString())
                                : null
                    });
                }

                object[] rawExpressions =
                    material is UMaterial concreteMaterial
                        ? concreteMaterial.Expressions
                            .Select((expression, index) =>
                            {
                                if (
                                    expression.TryLoad(
                                        out CUE4Parse.UE4.Assets.Exports.UObject
                                            loadedExpression) &&
                                    loadedExpression is not null)
                                {
                                    return (object)new
                                    {
                                        index,
                                        resolved = true,
                                        objectPath =
                                            loadedExpression.GetPathName(),
                                        exportType =
                                            loadedExpression.ExportType,
                                        properties =
                                            loadedExpression.Properties
                                                .OrderBy(
                                                    p => p.Name.Text,
                                                    StringComparer.Ordinal)
                                                .Select(p => new
                                                {
                                                    name = p.Name.Text,
                                                    valueType =
                                                        p.Tag?.GenericValue
                                                            ?.GetType()
                                                            .FullName,
                                                    value =
                                                        p.Tag?.GenericValue
                                                            ?.ToString()
                                                })
                                                .ToArray()
                                    };
                                }

                                return (object)new
                                {
                                    index,
                                    resolved = false,
                                    reference =
                                        expression.ToString()
                                };
                            })
                            .ToArray()
                        : Array.Empty<object>();

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
                    semanticResolved =
                        semantics.resolved,
                    blendMode =
                        (semantics.resolved
                            ? semantics.blendMode
                            : parameters.BlendMode).ToString(),
                    shadingModel =
                        (semantics.resolved
                            ? semantics.shadingModel
                            : parameters.ShadingModel).ToString(),
                    opacityMaskClipValue =
                        semantics.resolved
                            ? semantics.opacityMaskClipValue
                            : 0.333f,
                    twoSided =
                        semantics.resolved
                            ? semantics.twoSided
                            : (bool?)null,
                    disableDepthTest =
                        semantics.resolved
                            ? semantics.disableDepthTest
                            : (bool?)null,
                    canMaskedBeAssumedOpaque =
                        semantics.resolved
                            ? semantics.canMaskedBeAssumedOpaque
                            : (bool?)null,
                    isMasked =
                        (semantics.resolved
                            ? semantics.blendMode
                            : parameters.BlendMode) ==
                                EBlendMode.BLEND_Masked,
                    semanticParentDepth =
                        semantics.parentDepth,
                    semanticBlendOverride =
                        semantics.blendOverridden,
                    semanticShadingOverride =
                        semantics.shadingOverridden,
                    semanticOpacityMaskOverride =
                        semantics.opacityMaskOverridden,
                    semanticTwoSidedOverride =
                        semantics.twoSidedOverridden,
                    semanticBaseMaterialPath =
                        semantics.baseMaterialPath,
                    textureCount = textures.Count,
                    scalarCount = scalars.Length,
                    colorCount = colors.Length,
                    switchCount = switches.Length,
                    rawPropertyKeyCount = propertyKeys.Length,
                    rawExpressionCount = rawExpressions.Length,
                    rawExpressions,
                    textures,
                    scalars,
                    colors,
                    switches,
                    rawPropertyKeys = propertyKeys,
                    rawMaterialProperties =
                        material is UMaterial concreteGraphMaterial
                            ? DescribePropertyHolder(
                                concreteGraphMaterial.Properties)
                            : Array.Empty<object>(),
                    expressionGraph =
                        material is UMaterial graphMaterial
                            ? DescribeMaterialExpressions(
                                graphMaterial)
                            : Array.Empty<object>()
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
    semanticResolutionFailures.Count == 0 &&
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
    semanticResolutionFailures,
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


static (
    bool resolved,
    EBlendMode blendMode,
    EMaterialShadingModel shadingModel,
    float opacityMaskClipValue,
    bool twoSided,
    bool disableDepthTest,
    bool canMaskedBeAssumedOpaque,
    int parentDepth,
    bool blendOverridden,
    bool shadingOverridden,
    bool opacityMaskOverridden,
    bool twoSidedOverridden,
    string baseMaterialPath)
ResolveMaterialSemantics(
    UUnrealMaterial material,
    DefaultFileProvider provider,
    HashSet<string>? visiting = null)
{
    visiting ??=
        new HashSet<string>(
            StringComparer.OrdinalIgnoreCase);

    var path = material.GetPathName();
    if (!visiting.Add(path))
    {
        return (
            false,
            EBlendMode.BLEND_Opaque,
            EMaterialShadingModel.MSM_Unlit,
            0.333f,
            false,
            false,
            false,
            0,
            false,
            false,
            false,
            false,
            "");
    }

    try
    {
        if (material is UMaterial concrete)
        {
            return (
                true,
                concrete.BlendMode,
                concrete.ShadingModel,
                concrete.OpacityMaskClipValue,
                concrete.TwoSided,
                concrete.bDisableDepthTest,
                concrete.GetOrDefault<bool>(
                    "bCanMaskedBeAssumedOpaque"),
                0,
                false,
                false,
                false,
                false,
                concrete.GetPathName());
        }

        if (material is not UMaterialInstance instance)
        {
            return (
                false,
                EBlendMode.BLEND_Opaque,
                EMaterialShadingModel.MSM_Unlit,
                0.333f,
                false,
                false,
                false,
                0,
                false,
                false,
                false,
                false,
                "");
        }

        UUnrealMaterial? parent = instance.Parent;

        if (parent is null)
        {
            var rawParentProperty =
                instance.Properties.FirstOrDefault(
                    p => p.Name.Text.Equals(
                        "Parent",
                        StringComparison.Ordinal));

            if (
                rawParentProperty?.Tag?.GenericValue
                    is FPackageIndex rawParent)
            {
                if (
                    rawParent.TryLoad<UUnrealMaterial>(
                        out var loadedParent) &&
                    loadedParent is not null)
                {
                    parent = loadedParent;
                }
                else
                {
                    parent =
                        ResolveMaterialByRawReference(
                            provider,
                            rawParent.ToString());
                }
            }
        }

        if (parent is null)
        {
            return (
                false,
                EBlendMode.BLEND_Opaque,
                EMaterialShadingModel.MSM_Unlit,
                0.333f,
                false,
                false,
                false,
                0,
                false,
                false,
                false,
                false,
                "");
        }

        var inherited =
            ResolveMaterialSemantics(
                parent,
                provider,
                visiting);

        if (!inherited.resolved)
            return inherited;

        var blendMode =
            inherited.blendMode;
        var shadingModel =
            inherited.shadingModel;
        var opacityMaskClipValue =
            inherited.opacityMaskClipValue;
        var twoSided =
            inherited.twoSided;

        var blendOverridden = false;
        var shadingOverridden = false;
        var opacityMaskOverridden = false;
        var twoSidedOverridden = false;

        var rawOverrides =
            instance.GetOrDefault<FStructFallback?>(
                "BasePropertyOverrides");

        if (rawOverrides is not null)
        {
            if (rawOverrides.GetOrDefault<bool>(
                    "bOverride_BlendMode"))
            {
                blendMode =
                    rawOverrides.GetOrDefault<EBlendMode>(
                        "BlendMode",
                        blendMode);
                blendOverridden = true;
            }

            if (rawOverrides.GetOrDefault<bool>(
                    "bOverride_ShadingModel"))
            {
                shadingModel =
                    rawOverrides.GetOrDefault<
                        EMaterialShadingModel>(
                        "ShadingModel",
                        shadingModel);
                shadingOverridden = true;
            }

            if (rawOverrides.GetOrDefault<bool>(
                    "bOverride_OpacityMaskClipValue"))
            {
                opacityMaskClipValue =
                    rawOverrides.GetOrDefault<float>(
                        "OpacityMaskClipValue",
                        opacityMaskClipValue);
                opacityMaskOverridden = true;
            }

            if (rawOverrides.GetOrDefault<bool>(
                    "bOverride_TwoSided"))
            {
                if (!rawOverrides.TryGetValue<bool>(
                        out twoSided,
                        "TwoSided",
                        "bTwoSided"))
                {
                    twoSided =
                        inherited.twoSided;
                }
                twoSidedOverridden = true;
            }
        }

        return (
            true,
            blendMode,
            shadingModel,
            opacityMaskClipValue,
            twoSided,
            inherited.disableDepthTest,
            inherited.canMaskedBeAssumedOpaque,
            inherited.parentDepth + 1,
            blendOverridden,
            shadingOverridden,
            opacityMaskOverridden,
            twoSidedOverridden,
            inherited.baseMaterialPath);
    }
    finally
    {
        visiting.Remove(path);
    }
}


static UUnrealMaterial? ResolveMaterialByRawReference(
    DefaultFileProvider provider,
    string rawReference)
{
    if (string.IsNullOrWhiteSpace(rawReference))
        return null;

    var firstQuote = rawReference.IndexOf('\'');
    var lastQuote = rawReference.LastIndexOf('\'');
    var objectPath =
        firstQuote >= 0 &&
        lastQuote > firstQuote
            ? rawReference.Substring(
                firstQuote + 1,
                lastQuote - firstQuote - 1)
            : rawReference;

    objectPath =
        objectPath.Replace('\\', '/');

    if (objectPath.StartsWith(
            "/Game/",
            StringComparison.OrdinalIgnoreCase))
    {
        objectPath =
            objectPath.Substring("/Game/".Length);
    }
    else
    {
        objectPath =
            objectPath.TrimStart('/');
    }

    var slash = objectPath.LastIndexOf('/');
    var dot = objectPath.LastIndexOf('.');
    string objectName;
    string packageStem;

    if (dot > slash)
    {
        objectName =
            objectPath.Substring(dot + 1);
        packageStem =
            objectPath.Substring(0, dot);
    }
    else
    {
        packageStem = objectPath;
        objectName =
            slash >= 0
                ? objectPath.Substring(slash + 1)
                : objectPath;
    }

    var logicalPackage =
        packageStem + ".uasset";
    var resolvedPath =
        ResolveProviderPackagePath(
            provider,
            logicalPackage);

    if (resolvedPath is null)
        return null;

    try
    {
        return provider
            .LoadPackage(resolvedPath)
            .GetExports()
            .OfType<UUnrealMaterial>()
            .FirstOrDefault(
                material =>
                    material.GetPathName().EndsWith(
                        "." + objectName,
                        StringComparison.OrdinalIgnoreCase));
    }
    catch
    {
        return null;
    }
}


static object[] DescribePropertyHolder(
    IEnumerable<CUE4Parse.UE4.Assets.Objects.FPropertyTag>
        properties)
{
    return properties
        .Select(
            property => new {
                name = property.Name.Text,
                valueType =
                    property.Tag?.GenericValue?
                        .GetType().FullName,
                value =
                    DescribeDiagnosticValue(
                        property.Tag?.GenericValue)
            })
        .Cast<object>()
        .ToArray();
}

static object? DescribeDiagnosticValue(
    object? value,
    int depth = 0)
{
    if (value is null)
        return null;

    if (depth >= 4)
        return value.ToString();

    if (value is FPackageIndex packageIndex)
    {
        return new {
            kind = "FPackageIndex",
            index = packageIndex.Index,
            path = packageIndex.ToString()
        };
    }

    if (value is FScriptStruct scriptStruct)
    {
        if (
            scriptStruct.StructType
                is CUE4Parse.UE4.Objects.Engine.FExpressionInput
                    input)
        {
            return new {
                kind = "FExpressionInput",
                expressionIndex =
                    input.Expression?.Index,
                expressionPath =
                    input.Expression?.ToString(),
                outputIndex = input.OutputIndex,
                inputName = input.InputName.Text,
                expressionName =
                    input.ExpressionName.Text,
                mask = input.Mask,
                maskR = input.MaskR,
                maskG = input.MaskG,
                maskB = input.MaskB,
                maskA = input.MaskA,
                fallback =
                    input.FallbackStruct is null
                        ? null
                        : DescribeDiagnosticValue(
                            input.FallbackStruct,
                            depth + 1)
            };
        }

        return new {
            kind = "FScriptStruct",
            structType =
                scriptStruct.StructType
                    .GetType().FullName,
            value =
                scriptStruct.StructType.ToString()
        };
    }

    if (value is FStructFallback fallback)
    {
        return new {
            kind = "FStructFallback",
            properties = fallback.Properties
                .Select(
                    property => new {
                        name = property.Name.Text,
                        valueType =
                            property.Tag?.GenericValue?
                                .GetType().FullName,
                        value =
                            DescribeDiagnosticValue(
                                property.Tag?.GenericValue,
                                depth + 1)
                    })
                .ToArray()
        };
    }

    if (
        value is System.Collections.IEnumerable enumerable &&
        value is not string)
    {
        var values = new List<object?>();
        foreach (var item in enumerable)
        {
            if (values.Count >= 64)
                break;
            values.Add(
                DescribeDiagnosticValue(
                    item,
                    depth + 1));
        }
        return values.ToArray();
    }

    return value.ToString();
}

static object[] DescribeMaterialExpressions(
    UMaterial material)
{
    var rows = new List<object>();

    for (
        var expressionIndex = 0;
        expressionIndex < material.Expressions.Length;
        ++expressionIndex)
    {
        var reference =
            material.Expressions[expressionIndex];

        if (
            !reference.TryLoad(
                out CUE4Parse.UE4.Assets.Exports.UObject
                    expression) ||
            expression is null)
        {
            rows.Add(new {
                expressionIndex,
                reference = reference.ToString(),
                loaded = false
            });
            continue;
        }

        rows.Add(new {
            expressionIndex,
            reference = reference.ToString(),
            loaded = true,
            exportType = expression.ExportType,
            objectPath = expression.GetPathName(),
            properties =
                DescribePropertyHolder(
                    expression.Properties)
        });
    }

    return rows.ToArray();
}
