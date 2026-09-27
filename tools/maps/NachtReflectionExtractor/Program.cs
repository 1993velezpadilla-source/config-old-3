using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.BuildData;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Objects.Core.Misc;
using System.Reflection;
using System.Text.Json;

if (args.Length != 2)
{
    Console.Error.WriteLine(
        "usage: NachtReflectionExtractor <unpacked-root> <output-json>");
    return 2;
}

const BindingFlags Flags =
    BindingFlags.Instance |
    BindingFlags.Public |
    BindingFlags.NonPublic;

object? ReadMember(object target, string name)
{
    var type = target.GetType();

    var field = type.GetField(name, Flags);
    if (field is not null)
    {
        try { return field.GetValue(target); }
        catch { }
    }

    var property = type.GetProperty(name, Flags);
    if (
        property is not null &&
        property.GetIndexParameters().Length == 0 &&
        property.GetMethod is not null)
    {
        try { return property.GetValue(target); }
        catch { }
    }

    return null;
}

double? Number(object? value)
{
    if (value is null)
        return null;

    try
    {
        return Convert.ToDouble(
            value,
            System.Globalization.CultureInfo.InvariantCulture);
    }
    catch
    {
        return null;
    }
}

bool? Boolean(object? value)
{
    if (value is bool b)
        return b;

    if (
        value is not null &&
        bool.TryParse(
            value.ToString(),
            out var parsed))
        return parsed;

    return null;
}

string? Text(object? value)
{
    if (value is null)
        return null;

    var text = value.ToString();
    return string.IsNullOrWhiteSpace(text)
        ? null
        : text;
}

string? ReferencePath(object? value)
{
    if (value is null)
        return null;

    if (
        value is FPackageIndex packageIndex &&
        packageIndex.TryLoad<UObject>(
            out var loaded) &&
        loaded is not null)
    {
        var path = loaded.GetPathName();
        if (!string.IsNullOrWhiteSpace(path))
            return path;
    }

    return Text(value);
}

Dictionary<string, double>? Vector(
    object? value,
    string[] names)
{
    if (value is null)
        return null;

    var result =
        new Dictionary<string, double>(
            StringComparer.Ordinal);

    foreach (var name in names)
    {
        var number =
            Number(
                ReadMember(
                    value,
                    name));

        if (number is null)
            return null;

        result[name] = number.Value;
    }

    return result;
}

Dictionary<string, double>? LinearColor(
    object? value)
{
    return Vector(
        value,
        new[] { "R", "G", "B", "A" });
}

object? ResolveAttachParent(object current)
{
    var attach =
        ReadMember(
            current,
            "AttachParent");

    if (
        attach is FPackageIndex packageIndex &&
        packageIndex.TryLoad<USceneComponent>(
            out var parent) &&
        parent is not null)
    {
        return parent;
    }

    return null;
}

List<object> BuildHierarchy(object start)
{
    var rows = new List<object>();
    var seen =
        new HashSet<object>(
            ReferenceEqualityComparer.Instance);

    object? current = start;

    for (
        var depth = 0;
        current is not null && depth < 16;
        ++depth)
    {
        if (!seen.Add(current))
            throw new InvalidOperationException(
                "attachment cycle");

        var location =
            Vector(
                ReadMember(
                    current,
                    "RelativeLocation"),
                new[] { "X", "Y", "Z" });

        var rotation =
            Vector(
                ReadMember(
                    current,
                    "RelativeRotation"),
                new[] { "Pitch", "Yaw", "Roll" });

        var scale =
            Vector(
                ReadMember(
                    current,
                    "RelativeScale3D"),
                new[] { "X", "Y", "Z" });

        if (
            location is null ||
            rotation is null ||
            scale is null)
        {
            throw new InvalidOperationException(
                "component transform incomplete");
        }

        rows.Add(
            new {
                depth,
                name =
                    Text(
                        ReadMember(
                            current,
                            "Name"))
                    ?? current.GetType().Name,
                type =
                    current.GetType().FullName
                    ?? current.GetType().Name,
                locationUEcm = location,
                rotationUE = rotation,
                scale
            });

        current =
            ResolveAttachParent(current);
    }

    if (rows.Count == 0)
        throw new InvalidOperationException(
            "empty attachment chain");

    return rows;
}

string CaptureKind(string fullType)
{
    if (fullType.EndsWith(
            ".USphereReflectionCaptureComponent",
            StringComparison.Ordinal))
        return "sphere";

    if (fullType.EndsWith(
            ".UBoxReflectionCaptureComponent",
            StringComparison.Ordinal))
        return "box";

    if (fullType.EndsWith(
            ".UPlaneReflectionCaptureComponent",
            StringComparison.Ordinal))
        return "plane";

    if (
        fullType.Contains(
            "ReflectionCaptureComponent",
            StringComparison.Ordinal))
        return "generic";

    return "actor";
}

var provider =
    new DefaultFileProvider(
        args[0],
        SearchOption.AllDirectories,
        true,
        new VersionContainer(
            EGame.GAME_UE4_21));

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

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
        .Distinct(
            StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x)
        .ToArray();

if (maps.Length != 1)
{
    Console.Error.WriteLine(
        $"expected one Nacht_de_Untoten.umap, got {maps.Length}");
    return 3;
}

var exports =
    provider.LoadPackage(
        maps[0])
        .GetExports()
        .ToArray();

var skyRows = new List<object>();
var captureRows = new List<object>();
var captureCounts =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);
var captureComponentCount = 0;
var captureComponentBuildIds =
    new List<string>();

foreach (var export in exports)
{
    var fullType =
        export.GetType().FullName
        ?? export.GetType().Name;

    var sourcePath =
        export.GetPathName()
        ?? "";

    if (fullType.EndsWith(
            ".USkyLightComponent",
            StringComparison.Ordinal))
    {
        var skyHierarchy =
            export is USceneComponent
                ? BuildHierarchy(export)
                : new List<object>();

        skyRows.Add(
            new {
                componentName = export.Name.ToString(),
                sourceType = fullType,
                sourcePath,
                hierarchy = skyHierarchy,
                properties = new {
                    intensity =
                        Number(
                            ReadMember(
                                export,
                                "Intensity")),
                    lightColor =
                        Text(
                            ReadMember(
                                export,
                                "LightColor")),
                    sourceType =
                        Text(
                            ReadMember(
                                export,
                                "SourceType")),
                    cubemap =
                        ReferencePath(
                            ReadMember(
                                export,
                                "Cubemap")),
                    sourceCubemap =
                        ReferencePath(
                            ReadMember(
                                export,
                                "SourceCubemap")),
                    sourceCubemapAngleDegrees =
                        Number(
                            ReadMember(
                                export,
                                "SourceCubemapAngle")),
                    cubemapResolution =
                        Number(
                            ReadMember(
                                export,
                                "CubemapResolution")),
                    skyDistanceThresholdCm =
                        Number(
                            ReadMember(
                                export,
                                "SkyDistanceThreshold")),
                    lowerHemisphereColor =
                        LinearColor(
                            ReadMember(
                                export,
                                "LowerHemisphereColor")),
                    lowerHemisphereIsBlack =
                        Boolean(
                            ReadMember(
                                export,
                                "bLowerHemisphereIsBlack")),
                    realTimeCapture =
                        Boolean(
                            ReadMember(
                                export,
                                "bRealTimeCapture"))
                }
            });

        continue;
    }

    if (!fullType.Contains(
            "ReflectionCapture",
            StringComparison.Ordinal))
        continue;

    var kind =
        CaptureKind(fullType);

    captureCounts[kind] =
        captureCounts.TryGetValue(
            kind,
            out var count)
            ? count + 1
            : 1;

    var isComponent =
        fullType.Contains(
            "ReflectionCaptureComponent",
            StringComparison.Ordinal);

    string? mapBuildDataId = null;

    if (isComponent)
    {
        captureComponentCount++;

        try
        {
            var guid =
                export.GetOrDefault<FGuid>(
                    "MapBuildDataId");
            var guidText = guid.ToString();

            if (
                !string.IsNullOrWhiteSpace(
                    guidText) &&
                guidText.Any(
                    ch =>
                        ch != '0' &&
                        ch != '-' &&
                        ch != '{' &&
                        ch != '}'))
            {
                mapBuildDataId = guidText;
                captureComponentBuildIds.Add(
                    guidText);
            }
        }
        catch
        {
        }
    }

    var captureHierarchy =
        isComponent &&
        export is USceneComponent
            ? BuildHierarchy(export)
            : new List<object>();

    captureRows.Add(
        new {
            captureKind = kind,
            isComponent,
            exportName = export.Name.ToString(),
            sourceType = fullType,
            sourcePath,
            mapBuildDataId,
            hierarchy = captureHierarchy,
            properties = new {
                brightness =
                    Number(
                        ReadMember(
                            export,
                            "Brightness")),
                reflectionSourceType =
                    Text(
                        ReadMember(
                            export,
                            "ReflectionSourceType")),
                cubemap =
                    ReferencePath(
                        ReadMember(
                            export,
                            "Cubemap")),
                sourceCubemap =
                    ReferencePath(
                        ReadMember(
                            export,
                            "SourceCubemap")),
                influenceRadiusCm =
                    Number(
                        ReadMember(
                            export,
                            "InfluenceRadius")),
                boxTransitionDistanceCm =
                    Number(
                        ReadMember(
                            export,
                            "BoxTransitionDistance")),
                captureOffsetCm =
                    Vector(
                        ReadMember(
                            export,
                            "CaptureOffset"),
                        new[] { "X", "Y", "Z" }),
                cubemapAngleDegrees =
                    Number(
                        ReadMember(
                            export,
                            "CubemapAngle")),
                sourceCubemapAngleDegrees =
                    Number(
                        ReadMember(
                            export,
                            "SourceCubemapAngle")),
                visible =
                    Boolean(
                        ReadMember(
                            export,
                            "bVisible")),
                hiddenInGame =
                    Boolean(
                        ReadMember(
                            export,
                            "bHiddenInGame"))
            }
        });
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
        .Distinct(
            StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x)
        .ToArray();

var registryRows = new List<object>();
var reflectionBuildRows = new List<object>();
var linkedBuildDataCount = 0;

foreach (var candidate in builtDataCandidates)
{
    UObject[] candidateExports;

    try
    {
        candidateExports =
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
                registryCount = 0,
                reflectionCaptureBuildDataCount = 0
            });
        continue;
    }

    var registryCount = 0;
    var packageReflectionCount = 0;

    foreach (var candidateExport in candidateExports)
    {
        if (candidateExport is not
            UMapBuildDataRegistry registry)
            continue;

        registryCount++;

        var buildData =
            registry.ReflectionCaptureBuildData;

        if (buildData is null)
            continue;

        foreach (var pair in buildData)
        {
            var guid = pair.Key.ToString();
            var data = pair.Value;
            var linked =
                captureComponentBuildIds.Contains(
                    guid,
                    StringComparer.OrdinalIgnoreCase);

            if (linked)
                linkedBuildDataCount++;

            packageReflectionCount++;

            reflectionBuildRows.Add(
                new {
                    packagePath = candidate,
                    registryPath =
                        candidateExport.GetPathName()
                        ?? "",
                    mapBuildDataId = guid,
                    linkedToCapture = linked,
                    cubemapSize =
                        data.CubemapSize,
                    averageBrightness =
                        data.AverageBrightness,
                    brightness =
                        data.Brightness,
                    fullHdrCapturedBytes =
                        data.FullHDRCapturedData?.Length
                        ?? 0,
                    encodedCaptureData =
                        ReferencePath(
                            data.EncodedCaptureData)
                });
        }
    }

    registryRows.Add(
        new {
            packagePath = candidate,
            loadError = (string?)null,
            registryCount,
            reflectionCaptureBuildDataCount =
                packageReflectionCount
        });
}

if (skyRows.Count != 1)
{
    Console.Error.WriteLine(
        $"expected exactly one SkyLight component, got {skyRows.Count}");
    return 4;
}

var output = new {
    schemaVersion = 1,
    sourcePackage = maps[0],
    exportCount = exports.Length,
    skyLightCount = skyRows.Count,
    reflectionCaptureExportCount =
        captureRows.Count,
    reflectionCaptureComponentCount =
        captureComponentCount,
    reflectionCaptureTypeCounts =
        captureCounts,
    reflectionCaptureComponentBuildIds =
        captureComponentBuildIds,
    buildDataCandidateCount =
        builtDataCandidates.Length,
    buildDataCandidates,
    buildDataRegistryCount =
        registryRows.Sum(
            row =>
                (int)(row.GetType()
                    .GetProperty("registryCount")!
                    .GetValue(row) ?? 0)),
    reflectionCaptureBuildDataCount =
        reflectionBuildRows.Count,
    reflectionCaptureBuildDataLinkedCount =
        linkedBuildDataCount,
    skyLights = skyRows,
    reflectionCaptures = captureRows,
    buildDataRegistries = registryRows,
    reflectionCaptureBuildData =
        reflectionBuildRows
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
    "XZIEL_NACHT_REFLECTION_CENSUS_OK "
    + JsonSerializer.Serialize(
        new {
            output.skyLightCount,
            output.reflectionCaptureExportCount,
            output.reflectionCaptureComponentCount,
            output.reflectionCaptureTypeCounts,
            output.buildDataCandidateCount,
            output.buildDataRegistryCount,
            output.reflectionCaptureBuildDataCount,
            output.reflectionCaptureBuildDataLinkedCount
        }));

Console.WriteLine(
    "XZIEL_NACHT_REFLECTION_BUILDDATA_DATA "
    + JsonSerializer.Serialize(
        new {
            output.reflectionCaptureComponentBuildIds,
            output.buildDataCandidates,
            output.buildDataRegistries,
            output.reflectionCaptureBuildData
        }));

return 0;
