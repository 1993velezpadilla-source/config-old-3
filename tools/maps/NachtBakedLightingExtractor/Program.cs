using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.BuildData;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Component.StaticMesh;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse.UE4.Assets.Exports.FastGeoStreaming;
using CUE4Parse.UE4.Assets.Exports.Component.Landscape;
using CUE4Parse.UE4.Objects.Core.Misc;
using System.Text.Json;

if (args.Length != 2)
{
    Console.Error.WriteLine(
        "usage: NachtBakedLightingExtractor <unpacked-root> <output-json>");
    return 2;
}

string? ReferencePath(object? value)
{
    if (value is null)
        return null;

    if (
        value is FPackageIndex packageIndex &&
        packageIndex.TryLoad<UObject>(out var loaded) &&
        loaded is not null)
    {
        var path = loaded.GetPathName();
        if (!string.IsNullOrWhiteSpace(path))
            return path;
    }

    var text = value.ToString();
    return string.IsNullOrWhiteSpace(text) ? null : text;
}

bool IsNonZero(FGuid guid)
{
    var s = guid.ToString();
    return
        !string.IsNullOrWhiteSpace(s) &&
        s.Any(
            ch =>
                ch != '0' &&
                ch != '-' &&
                ch != '{' &&
                ch != '}');
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

var packageBasenames =
    provider.Files.Values
        .Where(f => f.IsUePackage)
        .Where(
            f => f.Path.EndsWith(
                ".uasset",
                StringComparison.OrdinalIgnoreCase))
        .GroupBy(
            f => Path.GetFileNameWithoutExtension(
                f.Path.Replace('\\', '/')),
            StringComparer.OrdinalIgnoreCase)
        .ToDictionary(
            g => g.Key,
            g => g.Select(x => x.Path).ToArray(),
            StringComparer.OrdinalIgnoreCase);

(string value, string source, string? ownerPath) ResolveMobility(
    UObject component)
{
    var visited =
        new HashSet<UObject>(
            ReferenceEqualityComparer.Instance);
    UObject? current = component;
    var depth = 0;

    while (current is not null && depth < 16)
    {
        if (!visited.Add(current))
            break;

        if (
            current.TryGetValue(
                out EComponentMobility mobility,
                "Mobility"))
        {
            return (
                mobility.ToString(),
                depth == 0 ? "component" : "template",
                current.GetPathName()
            );
        }

        current =
            current.Template?.Object?.Value
                as UObject;
        depth++;
    }

    return ("Unknown", "unresolved", null);
}

UStaticMesh? ResolveStaticMesh(
    UStaticMeshComponent component)
{
    try
    {
        var direct = component.GetLoadedStaticMesh();
        if (direct is not null)
            return direct;
    }
    catch
    {
    }

    var index = component.GetStaticMesh();
    var meshName = index.Name;

    if (string.IsNullOrWhiteSpace(meshName))
        return null;

    if (!packageBasenames.TryGetValue(
            meshName,
            out var candidates))
        return null;

    foreach (var packagePath in candidates)
    {
        try
        {
            var exports =
                provider.LoadPackage(packagePath)
                    .GetExports()
                    .OfType<UStaticMesh>()
                    .ToArray();

            var exact =
                exports.FirstOrDefault(
                    x => x.Name.Equals(
                        meshName,
                        StringComparison.OrdinalIgnoreCase));

            if (exact is not null)
                return exact;

            if (exports.Length == 1)
                return exports[0];
        }
        catch
        {
        }
    }

    return null;
}

var maps =
    provider.Files.Values
        .Where(
            f =>
                f.Path.EndsWith(
                    "/Nacht_de_Untoten.umap",
                    StringComparison.OrdinalIgnoreCase)
                || Path.GetFileName(f.Path).Equals(
                    "Nacht_de_Untoten.umap",
                    StringComparison.OrdinalIgnoreCase))
        .Select(f => f.Path)
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x)
        .ToArray();

if (maps.Length != 1)
{
    Console.Error.WriteLine(
        $"expected one Nacht_de_Untoten.umap, got {maps.Length}");
    return 3;
}

var mapExports =
    provider.LoadPackage(maps[0])
        .GetExports()
        .ToArray();

var mapExportIndexByObject =
    mapExports
        .Select((value, index) => new { value, index })
        .ToDictionary(x => x.value, x => x.index);

var componentBuildIds =
    new Dictionary<string, List<object>>(
        StringComparer.OrdinalIgnoreCase);
var lightMapCoordinateIndexCounts =
    new SortedDictionary<int, int>();

var unresolvedStaticMeshBindings =
    new List<object>();
var staticMeshComponents =
    new List<object>();
var staticMeshBuildBindingCount = 0;

void AddComponentBuildId(
    UObject export,
    FGuid guid,
    string bindingKind,
    int bindingIndex,
    string? assetPath,
    int lightMapCoordinateIndex,
    int numTexCoords = -1)
{
    if (!IsNonZero(guid))
        return;

    var key = guid.ToString();

    if (!componentBuildIds.TryGetValue(key, out var rows))
    {
        rows = new List<object>();
        componentBuildIds[key] = rows;
    }

    rows.Add(
        new {
            exportName = export.Name.ToString(),
            sourceType =
                export.GetType().FullName
                ?? export.GetType().Name,
            sourcePath =
                export.GetPathName()
                ?? "",
            componentExportIndex =
                mapExportIndexByObject[export],
            bindingKind,
            bindingIndex,
            assetPath,
            lightMapCoordinateIndex,
            numTexCoords
        });
}

foreach (var export in mapExports)
{
    try
    {
        if (
            export is UStaticMeshComponent staticMeshComponent &&
            staticMeshComponent.LODData is not null)
        {
            var loadedStaticMesh =
                ResolveStaticMesh(
                    staticMeshComponent);
            var staticMeshPath =
                loadedStaticMesh?.GetPathName()
                ?? ReferencePath(
                    staticMeshComponent.GetStaticMesh());
            var lightMapCoordinateIndex = -1;
            var numTexCoords = -1;
            var mobility =
                ResolveMobility(
                    staticMeshComponent);

            if (
                loadedStaticMesh?.RenderData?.LODs is { Length: > 0 } lods &&
                lods[0].VertexBuffer is not null)
            {
                numTexCoords =
                    lods[0].VertexBuffer.NumTexCoords;
            }

            if (
                loadedStaticMesh is not null &&
                loadedStaticMesh.TryGetValue(
                    out int authoredLightMapCoordinateIndex,
                    "LightMapCoordinateIndex"))
            {
                lightMapCoordinateIndex =
                    authoredLightMapCoordinateIndex;
            }
            else if (numTexCoords == 1)
            {
                /*
                 * With exactly one UV set, index 0 is the only valid authored
                 * lightmap coordinate channel. This is a data constraint, not
                 * a guessed default.
                 */
                lightMapCoordinateIndex = 0;
            }

            staticMeshComponents.Add(
                new {
                    componentExportIndex =
                        mapExportIndexByObject[export],
                    componentName =
                        staticMeshComponent.Name,
                    componentPath =
                        staticMeshComponent.GetPathName()
                        ?? "",
                    staticMeshPath,
                    loadedStaticMeshName =
                        loadedStaticMesh?.Name,
                    lightMapCoordinateIndex,
                    numTexCoords,
                    mobility = mobility.value,
                    mobilitySource = mobility.source,
                    mobilityOwnerPath = mobility.ownerPath,
                    lodCount =
                        staticMeshComponent.LODData.Length,
                    lodBuildDataIds =
                        staticMeshComponent.LODData
                            .Select(
                                x => x.MapBuildDataId.ToString())
                            .ToArray()
                });

            for (
                var lodIndex = 0;
                lodIndex < staticMeshComponent.LODData.Length;
                ++lodIndex)
            {
                var buildId =
                    staticMeshComponent
                        .LODData[lodIndex]
                        .MapBuildDataId;

                if (IsNonZero(buildId))
                {
                    staticMeshBuildBindingCount++;
                    lightMapCoordinateIndexCounts[
                        lightMapCoordinateIndex] =
                        lightMapCoordinateIndexCounts
                            .GetValueOrDefault(
                                lightMapCoordinateIndex)
                        + 1;


                    if (lightMapCoordinateIndex < 0)
                    {
                        unresolvedStaticMeshBindings.Add(
                            new {
                                componentName =
                                    staticMeshComponent.Name,
                                componentPath =
                                    staticMeshComponent.GetPathName()
                                    ?? "",
                                staticMeshPath,
                                loadedStaticMeshName =
                                    loadedStaticMesh?.Name,
                                numTexCoords
                            });
                    }
                }

                AddComponentBuildId(
                    export,
                    buildId,
                    "staticMeshLOD",
                    lodIndex,
                    staticMeshPath,
                    lightMapCoordinateIndex,
                    numTexCoords);
            }
        }

        if (export is UModelComponent modelComponent)
        {
            for (
                var elementIndex = 0;
                elementIndex < modelComponent.Elements.Length;
                ++elementIndex)
            {
                var buildId =
                    modelComponent
                        .Elements[elementIndex]
                        .MapBuildDataId;

                if (!buildId.HasValue)
                    continue;

                AddComponentBuildId(
                    export,
                    buildId.Value,
                    "modelElement",
                    elementIndex,
                    ReferencePath(
                        modelComponent
                            .Elements[elementIndex]
                            .Material),
                    -1);
            }
        }

        if (export is ULandscapeComponent landscapeComponent)
        {
            AddComponentBuildId(
                export,
                landscapeComponent.MapBuildDataId,
                "landscape",
                0,
                null,
                -1);
        }

        /*
         * Preserve the generic property path for component classes whose
         * build-data GUID is exposed as a regular tagged property rather than
         * native serialized LOD/model data.
         */
        var propertyGuid =
            export.GetOrDefault<FGuid>(
                "MapBuildDataId");

        AddComponentBuildId(
            export,
            propertyGuid,
            "property",
            0,
            null,
            -1);
    }
    catch
    {
    }
}

var builtDataCandidates =
    provider.Files.Values
        .Where(f => f.IsUePackage)
        .Select(f => f.Path)
        .Where(
            path =>
                path.EndsWith(
                    ".uasset",
                    StringComparison.OrdinalIgnoreCase) &&
                path.Contains(
                    "BuiltData",
                    StringComparison.OrdinalIgnoreCase) &&
                (path.Contains(
                     "UGC2755515831",
                     StringComparison.OrdinalIgnoreCase) ||
                 path.Contains(
                     "Nacht",
                     StringComparison.OrdinalIgnoreCase)))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x)
        .ToArray();

var registryRows = new List<object>();
var meshRows = new List<object>();
var volumeRows = new List<object>();
var volumetricRows = new List<object>();
var lightRows = new List<object>();

var registryCount = 0;
var meshBuildDataCount = 0;
var linkedMeshBuildDataCount = 0;
var lightMap1DCount = 0;
var lightMap2DCount = 0;
var shadowMap2DCount = 0;
var meshWithoutLightMapCount = 0;
var meshWithoutShadowMapCount = 0;
var perInstanceLightmapDataCount = 0;
var precomputedLightVolumeCount = 0;
var precomputedHighQualitySampleCount = 0;
var precomputedLowQualitySampleCount = 0;
var volumetricLightmapCount = 0;
var lightBuildDataCount = 0;
var staticShadowDepthSampleCount = 0;

var referencedLightmapTextures =
    new SortedSet<string>(StringComparer.Ordinal);
var referencedShadowmapTextures =
    new SortedSet<string>(StringComparer.Ordinal);
var referencedSkyOcclusionTextures =
    new SortedSet<string>(StringComparer.Ordinal);
var referencedAoMaskTextures =
    new SortedSet<string>(StringComparer.Ordinal);

foreach (var candidate in builtDataCandidates)
{
    UObject[] exports;

    try
    {
        exports =
            provider.LoadPackage(candidate)
                .GetExports()
                .ToArray();
    }
    catch (Exception e)
    {
        registryRows.Add(
            new {
                packagePath = candidate,
                loadError = e.Message,
                registryCount = 0
            });
        continue;
    }

    var packageRegistryCount = 0;

    foreach (var export in exports)
    {
        if (export is not UMapBuildDataRegistry registry)
            continue;

        registryCount++;
        packageRegistryCount++;

        if (registry.MeshBuildData is not null)
        {
            foreach (var pair in registry.MeshBuildData)
            {
                meshBuildDataCount++;

                var guid = pair.Key.ToString();
                var data = pair.Value;
                var linked =
                    componentBuildIds.ContainsKey(guid);

                if (linked)
                    linkedMeshBuildDataCount++;

                string lightMapType = "none";
                string shadowMapType = "none";
                var lightTextures = new List<string>();
                string? skyOcclusionTexture = null;
                string? aoMaskTexture = null;
                string? shadowTexture = null;

                if (data.LightMap is FLegacyLightMap1D)
                {
                    lightMapType = "1d";
                    lightMap1DCount++;
                }
                else if (data.LightMap is FLightMap2D lm2d)
                {
                    lightMapType = "2d";
                    lightMap2DCount++;

                    if (lm2d.Textures is not null)
                    {
                        foreach (var texture in lm2d.Textures)
                        {
                            var path = ReferencePath(texture);
                            if (path is null)
                                continue;
                            lightTextures.Add(path);
                            referencedLightmapTextures.Add(path);
                        }
                    }

                    skyOcclusionTexture =
                        ReferencePath(
                            lm2d.SkyOcclusionTexture);
                    if (skyOcclusionTexture is not null)
                        referencedSkyOcclusionTextures.Add(
                            skyOcclusionTexture);

                    aoMaskTexture =
                        ReferencePath(
                            lm2d.AOMaterialMaskTexture);
                    if (aoMaskTexture is not null)
                        referencedAoMaskTextures.Add(
                            aoMaskTexture);

                    shadowTexture =
                        ReferencePath(
                            lm2d.ShadowMapTexture);
                    if (shadowTexture is not null)
                        referencedShadowmapTextures.Add(
                            shadowTexture);
                }
                else
                {
                    meshWithoutLightMapCount++;
                }

                if (data.ShadowMap is FShadowMap2D sm2d)
                {
                    shadowMapType = "2d";
                    shadowMap2DCount++;
                    var path = ReferencePath(sm2d.Texture);
                    if (path is not null)
                    {
                        shadowTexture ??= path;
                        referencedShadowmapTextures.Add(path);
                    }
                }
                else
                {
                    meshWithoutShadowMapCount++;
                }

                var perInstance =
                    data.PerInstanceLightmapData?.Length
                    ?? 0;
                perInstanceLightmapDataCount +=
                    perInstance;

                meshRows.Add(
                    new {
                        packagePath = candidate,
                        registryPath =
                            export.GetPathName()
                            ?? "",
                        mapBuildDataId = guid,
                        linkedToMapComponent = linked,
                        linkedComponents =
                            linked
                                ? componentBuildIds[guid]
                                : new List<object>(),
                        lightMapType,
                        shadowMapType,
                        lightTextures,
                        skyOcclusionTexture,
                        aoMaskTexture,
                        shadowTexture,
                        lightGuids =
                            data.LightMap?.LightGuids
                                .Select(x => x.ToString())
                                .ToArray()
                            ?? Array.Empty<string>(),
                        shadowLightGuids =
                            data.ShadowMap?.LightGuids
                                .Select(x => x.ToString())
                                .ToArray()
                            ?? Array.Empty<string>(),
                        irrelevantLightCount =
                            data.IrrelevantLights?.Length
                            ?? 0,
                        perInstanceLightmapDataCount =
                            perInstance
                    });
            }
        }

        if (
            registry.LevelPrecomputedLightVolumeBuildData
            is not null)
        {
            foreach (
                var pair in
                registry.LevelPrecomputedLightVolumeBuildData)
            {
                var data = pair.Value;
                precomputedLightVolumeCount++;
                precomputedHighQualitySampleCount +=
                    data.HighQualitySamples?.Length
                    ?? 0;
                precomputedLowQualitySampleCount +=
                    data.LowQualitySamples?.Length
                    ?? 0;

                volumeRows.Add(
                    new {
                        packagePath = candidate,
                        mapBuildDataId =
                            pair.Key.ToString(),
                        sampleSpacing =
                            data.SampleSpacing,
                        numSHSamples =
                            data.NumSHSamples,
                        highQualitySamples =
                            data.HighQualitySamples?.Length
                            ?? 0,
                        lowQualitySamples =
                            data.LowQualitySamples?.Length
                            ?? 0
                    });
            }
        }

        if (
            registry.LevelPrecomputedVolumetricLightmapBuildData
            is not null)
        {
            foreach (
                var pair in
                registry.LevelPrecomputedVolumetricLightmapBuildData)
            {
                var data = pair.Value;
                volumetricLightmapCount++;

                volumetricRows.Add(
                    new {
                        packagePath = candidate,
                        mapBuildDataId =
                            pair.Key.ToString(),
                        brickSize = data.BrickSize,
                        indirectionDimensions =
                            data.IndirectionTextureDimensions.ToString(),
                        brickDataDimensions =
                            data.BrickDataDimensions.ToString(),
                        indirectionBytes =
                            data.IndirectionTexture.Data?.Length
                            ?? 0,
                        indirectionPixelFormat =
                            data.IndirectionTexture.PixelFormatString,
                        ambientVectorBytes =
                            data.BrickData.AmbientVector?.Data?.Length
                            ?? 0,
                        ambientVectorPixelFormat =
                            data.BrickData.AmbientVector?.PixelFormatString,
                        shCoefficientBytes =
                            data.BrickData.SHCoefficients?
                                .Sum(x => x?.Data?.Length ?? 0)
                            ?? 0,
                        skyBentNormalBytes =
                            data.BrickData.SkyBentNormal?.Data?.Length
                            ?? 0,
                        directionalShadowingBytes =
                            data.BrickData
                                .DirectionalLightShadowing?
                                .Data?
                                .Length
                            ?? 0
                    });
            }
        }

        if (registry.LightBuildData is not null)
        {
            foreach (var pair in registry.LightBuildData)
            {
                var data = pair.Value;
                lightBuildDataCount++;
                staticShadowDepthSampleCount +=
                    data.DepthMap.DepthSamples?.Length
                    ?? 0;

                lightRows.Add(
                    new {
                        packagePath = candidate,
                        mapBuildDataId =
                            pair.Key.ToString(),
                        shadowMapChannel =
                            data.ShadowMapChannel,
                        shadowMapSizeX =
                            data.DepthMap.ShadowMapSizeX,
                        shadowMapSizeY =
                            data.DepthMap.ShadowMapSizeY,
                        depthSampleCount =
                            data.DepthMap.DepthSamples?.Length
                            ?? 0
                    });
            }
        }
    }

    registryRows.Add(
        new {
            packagePath = candidate,
            loadError = (string?)null,
            registryCount = packageRegistryCount
        });
}

var output = new {
    schemaVersion = 1,
    sourcePackage = maps[0],
    mapExportCount = mapExports.Length,
    mapComponentBuildIdCount =
        componentBuildIds.Count,
    staticMeshBuildBindingCount,
    lightMapCoordinateIndexCounts,

    staticMeshComponentCount =
        staticMeshComponents.Count,
    staticMeshComponents,

    unresolvedStaticMeshBindingCount =
        unresolvedStaticMeshBindings.Count,
    unresolvedStaticMeshBindings,
    buildDataCandidateCount =
        builtDataCandidates.Length,
    buildDataRegistryCount =
        registryCount,
    meshBuildDataCount,
    linkedMeshBuildDataCount,
    lightMap1DCount,
    lightMap2DCount,
    shadowMap2DCount,
    meshWithoutLightMapCount,
    meshWithoutShadowMapCount,
    perInstanceLightmapDataCount,
    precomputedLightVolumeCount,
    precomputedHighQualitySampleCount,
    precomputedLowQualitySampleCount,
    volumetricLightmapCount,
    lightBuildDataCount,
    staticShadowDepthSampleCount,
    uniqueLightmapTextureCount =
        referencedLightmapTextures.Count,
    uniqueShadowmapTextureCount =
        referencedShadowmapTextures.Count,
    uniqueSkyOcclusionTextureCount =
        referencedSkyOcclusionTextures.Count,
    uniqueAoMaskTextureCount =
        referencedAoMaskTextures.Count,
    lightmapTextures =
        referencedLightmapTextures.ToArray(),
    shadowmapTextures =
        referencedShadowmapTextures.ToArray(),
    skyOcclusionTextures =
        referencedSkyOcclusionTextures.ToArray(),
    aoMaskTextures =
        referencedAoMaskTextures.ToArray(),
    buildDataCandidates = builtDataCandidates,
    buildDataRegistries = registryRows,
    meshBuildData = meshRows,
    precomputedLightVolumes = volumeRows,
    volumetricLightmaps = volumetricRows,
    lightBuildData = lightRows
};

Directory.CreateDirectory(
    Path.GetDirectoryName(
        Path.GetFullPath(args[1]))!);

File.WriteAllText(
    args[1],
    JsonSerializer.Serialize(
        output,
        new JsonSerializerOptions {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_NACHT_BAKED_LIGHTING_CENSUS_OK "
    + JsonSerializer.Serialize(
        new {
            output.buildDataRegistryCount,
            output.meshBuildDataCount,
            output.linkedMeshBuildDataCount,
            output.staticMeshBuildBindingCount,
            output.lightMapCoordinateIndexCounts,
            output.lightMap1DCount,
            output.lightMap2DCount,
            output.shadowMap2DCount,
            output.perInstanceLightmapDataCount,
            output.precomputedLightVolumeCount,
            output.precomputedHighQualitySampleCount,
            output.precomputedLowQualitySampleCount,
            output.volumetricLightmapCount,
            output.lightBuildDataCount,
            output.staticShadowDepthSampleCount,
            output.uniqueLightmapTextureCount,
            output.uniqueShadowmapTextureCount,
            output.uniqueSkyOcclusionTextureCount,
            output.uniqueAoMaskTextureCount
        }));

return 0;
