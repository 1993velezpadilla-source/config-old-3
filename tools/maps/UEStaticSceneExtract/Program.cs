using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Component.StaticMesh;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length != 6)
{
    Console.Error.WriteLine(
        "usage: UEStaticSceneExtract <unpacked-root> <mappings.usmap> <class-census.json> <xzms-report.json> <output.json> <source-game>");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var xzmsReportPath = args[3];
var outputPath = args[4];
var sourceGameName = args[5];

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
using var xzmsDoc = JsonDocument.Parse(File.ReadAllText(xzmsReportPath));

var mapPackages = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Select(row =>
        NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("packagePath missing")))
    .Where(path => path.EndsWith(
        ".umap",
        StringComparison.OrdinalIgnoreCase))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
    .ToArray();

var nativeMeshes = new Dictionary<string, NativeMesh>(
    StringComparer.OrdinalIgnoreCase);
var nativeMeshesCanonical = new Dictionary<string, NativeMesh>(
    StringComparer.OrdinalIgnoreCase);

foreach (var row in xzmsDoc.RootElement
             .GetProperty("meshes")
             .EnumerateArray())
{
    var objectPath =
        row.GetProperty("objectPath").GetString()
        ?? throw new InvalidDataException(
            "XZMS report mesh objectPath missing");
    var file =
        row.GetProperty("file").GetString()
        ?? throw new InvalidDataException(
            "XZMS report mesh file missing");
    var sourceIndex = row.GetProperty("index").GetInt32();
    var sourceMaterialCount =
        row.GetProperty("sourceMaterialCount").GetInt32();
    var sourceSectionMaterialIndices =
        row.GetProperty("sourceSectionMaterialIndices")
            .EnumerateArray()
            .Select(value => value.GetInt32())
            .ToArray();

    var nativeRow = new NativeMesh(
        objectPath,
        file,
        sourceIndex,
        sourceMaterialCount,
        sourceSectionMaterialIndices);

    if (!nativeMeshes.TryAdd(objectPath, nativeRow))
    {
        throw new InvalidDataException(
            "duplicate XZMS objectPath: " + objectPath);
    }

    var canonicalObjectPath = CanonicalObjectPath(objectPath);
    if (!nativeMeshesCanonical.TryAdd(
            canonicalObjectPath,
            nativeRow))
    {
        var existing =
            nativeMeshesCanonical[canonicalObjectPath];
        if (!string.Equals(
                existing.ObjectPath,
                objectPath,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException(
                "duplicate canonical XZMS objectPath: " +
                canonicalObjectPath);
        }
    }
}

if (mapPackages.Length == 0)
    throw new InvalidDataException("no .umap packages in source census");
if (nativeMeshes.Count == 0)
    throw new InvalidDataException("XZMS report has no meshes");

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

// UE4.21 cooked Blueprint/component instances can omit properties that are
// inherited from their archetype/template or generated class. Nacht does this
// heavily for StaticMeshComponent.StaticMesh. Allow CUE4Parse's property
// resolver to follow those authoritative defaults before declaring a mesh null.
PropertyUtil.SearchPropertyInTemplate = true;

var packageFailures = new List<object>();
var componentFailures = new List<object>();
var unresolvedMeshes = new SortedSet<string>(
    StringComparer.OrdinalIgnoreCase);
var candidates = new List<SceneCandidate>();
var actorAnchors = new List<object>();
var worldCache = new Dictionary<string, FTransform>(
    StringComparer.Ordinal);
var visiting = new HashSet<string>(
    StringComparer.Ordinal);

var packagesLoaded = 0;
var staticComponents = 0;
var instancedComponents = 0;
var instancedRows = 0;
var absoluteTransformComponents = 0;
var nullMeshComponents = 0;
var loadedMeshComponents = 0;
var resolvedMeshReferenceComponents = 0;
var nonFiniteMatrices = 0;
var componentsWithMaterialOverrides = 0;
var overrideMaterialSlotCount = 0;
var nonNullOverrideMaterialSlotCount = 0;
var componentsWithEffectiveMaterialOverrides = 0;
var effectiveOverrideMaterialSlotCount = 0;
var effectiveOverrideSubmeshCount = 0;

foreach (var logicalPackage in mapPackages)
{
    var resolved = ResolveProviderPackagePath(
        provider,
        logicalPackage);
    if (resolved is null)
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
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        var packageExports = Enumerable
            .Range(0, package.ExportMapLength)
            .Select(index => package.GetExport(index))
            .ToArray();

        var sceneComponents = packageExports
            .OfType<USceneComponent>()
            .OrderBy(
                value => value.GetPathName(),
                StringComparer.Ordinal)
            .ToArray();

        for (var exportIndex = 0;
             exportIndex < package.ExportMapLength;
             ++exportIndex)
        {
            var sourceObject =
                packageExports[exportIndex];
            FPackageIndex? rootReference = null;
            USceneComponent? rootComponent = null;
            var anchorSource = "";

            try
            {
                rootReference =
                    sourceObject.GetOrDefault<FPackageIndex>(
                        "RootComponent");
            }
            catch
            {
                rootReference = null;
            }

            if (rootReference is { IsNull: false })
            {
                rootComponent =
                    rootReference.Load<USceneComponent>();
                if (rootComponent is not null)
                    anchorSource =
                        "RootComponentProperty";
            }

            /*
             * Blueprint actor instances can inherit their root component from
             * class/SCS data, so the RootComponent property may be omitted
             * from the cooked instance. In that case use the actual scene
             * component exported under the actor's Outer chain. This preserves
             * UE ownership semantics instead of guessing from class names.
             */
            if (rootComponent is null)
            {
                var actorPath =
                    sourceObject.GetPathName();

                rootComponent = sceneComponents
                    .Where(component =>
                        ObjectOwnedBy(
                            component,
                            actorPath))
                    .Where(component =>
                    {
                        var parent =
                            component.GetAttachParent();
                        return parent is null ||
                            !ObjectOwnedBy(
                                parent,
                                actorPath);
                    })
                    .OrderBy(
                        component =>
                            component.GetPathName(),
                        StringComparer.Ordinal)
                    .FirstOrDefault();

                if (rootComponent is not null)
                    anchorSource =
                        "OwnedSceneComponent";
            }

            if (rootComponent is null)
                continue;

            var world =
                ResolveWorldTransform(
                    rootComponent,
                    worldCache,
                    visiting);
            var matrix =
                ToXzielMatrix(world);

            if (!FiniteMatrix(matrix))
                throw new InvalidDataException(
                    "non-finite actor anchor transform");

            object? sourceGameplayProperties = null;
            if (string.Equals(
                    sourceObject.ExportType,
                    "MysteryBoxLocation_C",
                    StringComparison.OrdinalIgnoreCase))
            {
                // Preserve exact per-instance Mystery Box location overrides
                // from the cooked UMAP. PropertyUtil.SearchPropertyInTemplate
                // is enabled above, so omitted values resolve through the
                // authoritative class/archetype defaults rather than guesses.
                var powerSwitchFlags =
                    sourceObject.GetOrDefault<FName[]>(
                        "PowerSwitchFlags")
                    ?? Array.Empty<FName>();

                sourceGameplayProperties = new
                {
                    alwaySpawnHereFirst =
                        sourceObject.GetOrDefault<bool>(
                            "AlwaySpawnHereFirst"),
                    boxRequiresPowerInstead =
                        sourceObject.GetOrDefault<bool>(
                            "BoxRequiresPowerInstead"),
                    hideMysteryBoxLocation =
                        sourceObject.GetOrDefault<bool>(
                            "HideMysteryBoxLocation"),
                    powered =
                        sourceObject.GetOrDefault<bool>(
                            "Powered"),
                    powerSwitchFlags =
                        powerSwitchFlags
                            .Select(value => value.ToString())
                            .ToArray()
                };
            }

            actorAnchors.Add(new
            {
                packagePath = logicalPackage,
                exportIndex,
                objectPath =
                    sourceObject.GetPathName(),
                className =
                    sourceObject.ExportType,
                rootComponentPath =
                    rootComponent.GetPathName(),
                anchorSource,
                matrixRowMajor = matrix,
                positionMeters = new[]
                {
                    matrix[3],
                    matrix[7],
                    matrix[11]
                },
                sourceGameplayProperties
            });
        }

        var components = packageExports
            .OfType<UStaticMeshComponent>()
            .OrderBy(
                value => value.GetPathName(),
                StringComparer.Ordinal)
            .ToArray();

        foreach (var component in components)
        {
            staticComponents++;

            try
            {
                if (component.GetOrDefault<bool>(
                        "bAbsoluteLocation") ||
                    component.GetOrDefault<bool>(
                        "bAbsoluteRotation") ||
                    component.GetOrDefault<bool>(
                        "bAbsoluteScale"))
                {
                    absoluteTransformComponents++;
                    throw new InvalidDataException(
                        "absolute scene-component transform requires explicit semantics");
                }

                var mesh = component.GetLoadedStaticMesh();
                string? meshPath = null;

                if (mesh is not null)
                {
                    loadedMeshComponents++;
                    meshPath = mesh.GetPathName();
                }
                else
                {
                    // UE4.21 cooked Blueprint components can retain the exact
                    // StaticMesh FPackageIndex while provider-side loading
                    // fails because the cooked import uses /Game virtual
                    // paths and the unpacked provider uses Pavlov/Content.
                    // Preserve the source reference itself and resolve it
                    // against the already-converted XZMS object-path catalog.
                    var meshReference = component.GetStaticMesh();
                    if (!meshReference.IsNull)
                    {
                        meshPath =
                            meshReference.ResolvedObject?.GetPathName();
                        if (!string.IsNullOrWhiteSpace(meshPath))
                            resolvedMeshReferenceComponents++;
                    }
                }

                if (string.IsNullOrWhiteSpace(meshPath))
                {
                    nullMeshComponents++;
                    continue;
                }

                NativeMesh? nativeMesh = null;
                if (!nativeMeshes.TryGetValue(
                        meshPath,
                        out nativeMesh))
                {
                    nativeMeshesCanonical.TryGetValue(
                        CanonicalObjectPath(meshPath),
                        out nativeMesh);
                }

                if (nativeMesh is null)
                {
                    unresolvedMeshes.Add(meshPath);
                    continue;
                }

                var materialOverrides = component.OverrideMaterials
                    .Select(material =>
                        material is { IsNull: false }
                            ? material.ResolvedObject?.GetPathName()
                                ?? material.Name
                            : null)
                    .ToArray();

                var nonNullOverrides =
                    materialOverrides.Count(path =>
                        !string.IsNullOrWhiteSpace(path));

                if (materialOverrides.Length > 0)
                {
                    componentsWithMaterialOverrides++;
                    overrideMaterialSlotCount +=
                        materialOverrides.Length;
                    nonNullOverrideMaterialSlotCount +=
                        nonNullOverrides;
                }

                var effectiveMaterialOverrides =
                    nativeMesh.SourceSectionMaterialIndices
                        .Where(slot =>
                            slot >= 0 &&
                            slot < nativeMesh.SourceMaterialCount)
                        .Distinct()
                        .Where(slot =>
                            slot < materialOverrides.Length &&
                            !string.IsNullOrWhiteSpace(
                                materialOverrides[slot]))
                        .OrderBy(slot => slot)
                        .Select(slot =>
                            new MaterialOverride(
                                slot,
                                materialOverrides[slot]!))
                        .ToArray();

                if (effectiveMaterialOverrides.Length > 0)
                {
                    componentsWithEffectiveMaterialOverrides++;
                    effectiveOverrideMaterialSlotCount +=
                        effectiveMaterialOverrides.Length;

                    var effectiveSlots =
                        effectiveMaterialOverrides
                            .Select(row => row.SlotIndex)
                            .ToHashSet();

                    effectiveOverrideSubmeshCount +=
                        nativeMesh.SourceSectionMaterialIndices.Count(
                            slot => effectiveSlots.Contains(slot));
                }

                var componentWorld = ResolveWorldTransform(
                    component,
                    worldCache,
                    visiting);

                if (component is UInstancedStaticMeshComponent instanced)
                {
                    instancedComponents++;
                    var rows = instanced.GetInstances();

                    if (rows.Length == 0)
                    {
                        /*
                         * A cooked ISM with no instance rows contributes no
                         * visible geometry and is intentionally omitted.
                         */
                        continue;
                    }

                    for (var instanceIndex = 0;
                         instanceIndex < rows.Length;
                         ++instanceIndex)
                    {
                        var world =
                            rows[instanceIndex].TransformData *
                            componentWorld;
                        var matrix = ToXzielMatrix(world);
                        if (!FiniteMatrix(matrix))
                        {
                            nonFiniteMatrices++;
                            throw new InvalidDataException(
                                "non-finite instanced transform");
                        }

                        candidates.Add(new SceneCandidate(
                            nativeMesh,
                            component.GetPathName(),
                            instanceIndex,
                            matrix,
                            effectiveMaterialOverrides));
                        instancedRows++;
                    }
                }
                else
                {
                    var matrix =
                        ToXzielMatrix(componentWorld);
                    if (!FiniteMatrix(matrix))
                    {
                        nonFiniteMatrices++;
                        throw new InvalidDataException(
                            "non-finite static transform");
                    }

                    candidates.Add(new SceneCandidate(
                        nativeMesh,
                        component.GetPathName(),
                        null,
                        matrix,
                        effectiveMaterialOverrides));
                }
            }
            catch (Exception e)
            {
                componentFailures.Add(new
                {
                    packagePath = logicalPackage,
                    componentPath = component.GetPathName(),
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
            resolvedPath = resolved,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var usedNativeMeshes = candidates
    .Select(row => row.Mesh)
    .DistinctBy(row => row.ObjectPath, StringComparer.OrdinalIgnoreCase)
    .OrderBy(row => row.SourceIndex)
    .ToArray();

var sceneMeshIndex = usedNativeMeshes
    .Select((row, index) => new { row.ObjectPath, Index = index })
    .ToDictionary(
        row => row.ObjectPath,
        row => row.Index,
        StringComparer.OrdinalIgnoreCase);

var meshRows = usedNativeMeshes
    .Select((row, index) => new
    {
        index,
        sourceObjectPath = row.ObjectPath,
        sourceXzmsIndex = row.SourceIndex,
        runtimeFile = row.File
    })
    .ToArray();

var instanceRows = candidates
    .Select((row, index) => new
    {
        instanceId = row.InstanceIndex is int local
            ? $"ue_instance_{index:D6}_{local:D6}"
            : $"ue_instance_{index:D6}",
        meshIndex = sceneMeshIndex[row.Mesh.ObjectPath],
        sourceComponentPath = row.ComponentPath,
        sourceInstanceIndex = row.InstanceIndex,
        materialOverrides = row.MaterialOverrides,
        matrixRowMajor = row.Matrix
    })
    .ToArray();

var ready =
    packagesLoaded == mapPackages.Length &&
    packageFailures.Count == 0 &&
    componentFailures.Count == 0 &&
    unresolvedMeshes.Count == 0 &&
    absoluteTransformComponents == 0 &&
    nonFiniteMatrices == 0 &&
    meshRows.Length > 0 &&
    instanceRows.Length > 0;

var output = new
{
    schemaVersion = 1,
    format = "xziel_visual_scene_v1",
    sourceGameName,
    coordinateSystem = new
    {
        source = "Unreal X,Y,Z centimeters",
        runtime = "XZIEL X,-Y,Z meters",
        matrixConvention =
            "row_major_column_vector_T_R_S",
        centimetersToMeters = 0.01
    },
    summary = new
    {
        mapPackageCount = mapPackages.Length,
        packagesLoaded,
        staticComponents,
        instancedComponents,
        instancedRows,
        nullMeshComponents,
        loadedMeshComponents,
        resolvedMeshReferenceComponents,
        componentsWithMaterialOverrides,
        overrideMaterialSlotCount,
        nonNullOverrideMaterialSlotCount,
        componentsWithEffectiveMaterialOverrides,
        effectiveOverrideMaterialSlotCount,
        effectiveOverrideSubmeshCount,
        sourceNativeMeshCount = nativeMeshes.Count,
        actorAnchorCount = actorAnchors.Count,
        referencedNativeMeshCount = meshRows.Length,
        sceneInstanceCount = instanceRows.Length,
        unresolvedMeshCount = unresolvedMeshes.Count,
        absoluteTransformComponents,
        nonFiniteMatrices,
        packageFailureCount = packageFailures.Count,
        componentFailureCount = componentFailures.Count,
        ready
    },
    mapPackages,
    actorAnchors = actorAnchors
        .OrderBy(
            row => JsonSerializer.Serialize(row),
            StringComparer.Ordinal)
        .ToArray(),
    unresolvedMeshes = unresolvedMeshes.ToArray(),
    packageFailures,
    componentFailures,
    meshes = meshRows,
    instances = instanceRows
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        output,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_STATIC_SCENE_EXTRACT " +
    JsonSerializer.Serialize(output.summary));

foreach (var mesh in unresolvedMeshes.Take(40))
{
    Console.WriteLine(
        "XZIEL_UE_STATIC_SCENE_UNRESOLVED_MESH " +
        mesh);
}

foreach (var failure in componentFailures.Take(40))
{
    Console.WriteLine(
        "XZIEL_UE_STATIC_SCENE_COMPONENT_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_STATIC_SCENE_EXTRACT_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_STATIC_SCENE_EXTRACT_GREEN");
return 0;

static bool ObjectOwnedBy(
    UObject source,
    string ownerPath)
{
    if (source is null ||
        string.IsNullOrWhiteSpace(ownerPath))
        return false;

    var outer = source.Outer;
    var depth = 0;

    while (outer is not null && depth++ < 64)
    {
        if (!outer.TryLoad(out var loaded) ||
            loaded is null)
            return false;

        if (string.Equals(
                loaded.GetPathName(),
                ownerPath,
                StringComparison.OrdinalIgnoreCase))
            return true;

        outer = loaded.Outer;
    }

    return false;
}

static FTransform ResolveWorldTransform(
    USceneComponent component,
    Dictionary<string, FTransform> cache,
    HashSet<string> visiting)
{
    var key = component.GetPathName();
    if (cache.TryGetValue(key, out var cached))
        return cached;

    if (!visiting.Add(key))
        throw new InvalidDataException(
            "scene attachment cycle at " + key);

    var local = component.GetRelativeTransform();
    var parent = component.GetAttachParent();
    FTransform world;

    if (parent is null)
    {
        world = local;
    }
    else
    {
        if (parent.GetOrDefault<bool>("bAbsoluteLocation") ||
            parent.GetOrDefault<bool>("bAbsoluteRotation") ||
            parent.GetOrDefault<bool>("bAbsoluteScale"))
        {
            throw new InvalidDataException(
                "absolute parent transform requires explicit semantics");
        }

        world = local * ResolveWorldTransform(
            parent,
            cache,
            visiting);
    }

    visiting.Remove(key);
    cache[key] = world;
    return world;
}

static float[] ToXzielMatrix(FTransform transform)
{
    var ue = transform.ToMatrixWithScale();

    /*
     * CUE4Parse's FMatrix mirrors Unreal's row-vector layout, including
     * translation in M30..M32. XZSC uses row-major storage with column-vector
     * math, so transpose first, then apply B*M*B for the X,-Y,Z basis.
     */
    var transposed = new double[]
    {
        ue.M00, ue.M10, ue.M20, ue.M30,
        ue.M01, ue.M11, ue.M21, ue.M31,
        ue.M02, ue.M12, ue.M22, ue.M32,
        ue.M03, ue.M13, ue.M23, ue.M33
    };

    var result = new float[16];
    for (var row = 0; row < 4; ++row)
    {
        for (var column = 0; column < 4; ++column)
        {
            var value = transposed[row * 4 + column];

            if (row == 1)
                value = -value;
            if (column == 1)
                value = -value;

            if (column == 3 && row < 3)
                value *= 0.01;

            if (!double.IsFinite(value))
                throw new InvalidDataException(
                    "non-finite transform matrix value");

            result[row * 4 + column] =
                checked((float)value);
        }
    }

    if (MathF.Abs(result[12]) > 1.0e-5f ||
        MathF.Abs(result[13]) > 1.0e-5f ||
        MathF.Abs(result[14]) > 1.0e-5f ||
        MathF.Abs(result[15] - 1.0f) > 1.0e-5f)
    {
        throw new InvalidDataException(
            "transform is not affine after basis conversion");
    }

    return result;
}

static bool FiniteMatrix(float[] matrix)
    => matrix.Length == 16 &&
       matrix.All(float.IsFinite);

static string CanonicalObjectPath(string value)
{
    var path = value.Replace('\\', '/');

    var pavlovContent = path.IndexOf(
        "/Pavlov/Content/",
        StringComparison.OrdinalIgnoreCase);
    if (pavlovContent >= 0)
    {
        path = "/Game/" + path[
            (pavlovContent + "/Pavlov/Content/".Length)..];
    }
    else if (path.StartsWith(
        "Pavlov/Content/",
        StringComparison.OrdinalIgnoreCase))
    {
        path = "/Game/" +
            path["Pavlov/Content/".Length..];
    }
    else if (path.StartsWith(
        "Content/",
        StringComparison.OrdinalIgnoreCase))
    {
        path = "/Game/" +
            path["Content/".Length..];
    }
    else
    {
        var content = path.IndexOf(
            "/Content/",
            StringComparison.OrdinalIgnoreCase);
        if (content >= 0 &&
            !path.StartsWith(
                "/Game/",
                StringComparison.OrdinalIgnoreCase))
        {
            path = "/Game/" +
                path[(content + "/Content/".Length)..];
        }
    }

    return path.Trim();
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
        .ThenBy(key => key, StringComparer.OrdinalIgnoreCase)
        .FirstOrDefault();
}

sealed record NativeMesh(
    string ObjectPath,
    string File,
    int SourceIndex,
    int SourceMaterialCount,
    int[] SourceSectionMaterialIndices);

sealed record MaterialOverride(
    int SlotIndex,
    string ObjectPath);

sealed record SceneCandidate(
    NativeMesh Mesh,
    string ComponentPath,
    int? InstanceIndex,
    float[] Matrix,
    MaterialOverride[] MaterialOverrides);
