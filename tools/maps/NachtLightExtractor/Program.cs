using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Assets.Exports.Component;
using System.Reflection;
using System.Text.Json;

if (args.Length != 2)
{
    Console.Error.WriteLine("usage: NachtLightExtractor <unpacked-root> <output-json>");
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
        bool.TryParse(value.ToString(), out var parsed))
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
        var number = Number(
            ReadMember(value, name));

        if (number is null)
            return null;

        result[name] = number.Value;
    }

    return result;
}

Dictionary<string, int>? Color(
    object? value)
{
    if (value is null)
        return null;

    var result =
        new Dictionary<string, int>(
            StringComparer.Ordinal);

    var complete = true;
    foreach (var name in new[] { "R", "G", "B", "A" })
    {
        var number = Number(
            ReadMember(value, name));

        if (number is null)
        {
            complete = false;
            break;
        }

        result[name] =
            Math.Clamp(
                (int)Math.Round(number.Value),
                0,
                255);
    }

    if (complete)
        return result;

    var text =
        (value.ToString() ?? "")
            .Trim()
            .TrimStart('#');

    if (
        text.Length == 6 &&
        int.TryParse(
            text,
            System.Globalization.NumberStyles.HexNumber,
            null,
            out var rgb))
    {
        return new Dictionary<string, int> {
            ["R"] = (rgb >> 16) & 0xff,
            ["G"] = (rgb >> 8) & 0xff,
            ["B"] = rgb & 0xff,
            ["A"] = 255
        };
    }

    if (
        text.Length == 8 &&
        uint.TryParse(
            text,
            System.Globalization.NumberStyles.HexNumber,
            null,
            out var rgba))
    {
        return new Dictionary<string, int> {
            ["R"] = (int)((rgba >> 24) & 0xff),
            ["G"] = (int)((rgba >> 16) & 0xff),
            ["B"] = (int)((rgba >> 8) & 0xff),
            ["A"] = (int)(rgba & 0xff)
        };
    }

    return null;
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

string Kind(string fullType)
{
    if (fullType.EndsWith(
            ".UPointLightComponent",
            StringComparison.Ordinal))
        return "point";

    if (fullType.EndsWith(
            ".USpotLightComponent",
            StringComparison.Ordinal))
        return "spot";

    if (fullType.EndsWith(
            ".UDirectionalLightComponent",
            StringComparison.Ordinal))
        return "directional";

    if (fullType.EndsWith(
            ".USkyLightComponent",
            StringComparison.Ordinal))
        return "sky";

    return "";
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

var rows =
    new List<object>();

var counts =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);

foreach (var export in exports)
{
    var fullType =
        export.GetType().FullName
        ?? export.GetType().Name;

    var kind = Kind(fullType);
    if (kind.Length == 0)
        continue;

    var hierarchy =
        BuildHierarchy(export);

    var intensity =
        Number(
            ReadMember(
                export,
                "Intensity"));

    var lightColor =
        Color(
            ReadMember(
                export,
                "LightColor"));

    var radius =
        Number(
            ReadMember(
                export,
                "AttenuationRadius"));

    var innerCone =
        Number(
            ReadMember(
                export,
                "InnerConeAngle"));

    var outerCone =
        Number(
            ReadMember(
                export,
                "OuterConeAngle"));

    var units =
        Text(
            ReadMember(
                export,
                "IntensityUnits"));

    var inverseSquared =
        Boolean(
            ReadMember(
                export,
                "bUseInverseSquaredFalloff"));

    var falloffExponent =
        Number(
            ReadMember(
                export,
                "LightFalloffExponent"));

    var sourceRadius =
        Number(
            ReadMember(
                export,
                "SourceRadius"));

    var softSourceRadius =
        Number(
            ReadMember(
                export,
                "SoftSourceRadius"));

    var sourceLength =
        Number(
            ReadMember(
                export,
                "SourceLength"));

    var temperature =
        Number(
            ReadMember(
                export,
                "Temperature"));

    var useTemperature =
        Boolean(
            ReadMember(
                export,
                "bUseTemperature"));

    var castShadows =
        Boolean(
            ReadMember(
                export,
                "CastShadows"));

    var visible =
        Boolean(
            ReadMember(
                export,
                "bVisible"));

    if (
        intensity is null ||
        lightColor is null)
    {
        throw new InvalidOperationException(
            $"required light properties missing: {export.GetPathName()}");
    }

    if (
        (kind == "point" ||
         kind == "spot") &&
        (radius is null ||
         units is null ||
         inverseSquared is null ||
         falloffExponent is null ||
         sourceRadius is null ||
         softSourceRadius is null ||
         sourceLength is null))
    {
        throw new InvalidOperationException(
            $"point/spot properties incomplete: {export.GetPathName()}");
    }

    if (
        kind == "spot" &&
        (innerCone is null ||
         outerCone is null))
    {
        throw new InvalidOperationException(
            $"spot cone properties incomplete: {export.GetPathName()}");
    }

    if (
        kind != "sky" &&
        (temperature is null ||
         useTemperature is null))
    {
        throw new InvalidOperationException(
            $"temperature properties incomplete: {export.GetPathName()}");
    }

    if (castShadows is null)
    {
        throw new InvalidOperationException(
            $"CastShadows missing: {export.GetPathName()}");
    }

    var actorPath =
        export.GetPathName() ?? "";

    var lastDot =
        actorPath.LastIndexOf('.');

    var parentPath =
        lastDot > 0
            ? actorPath[..lastDot]
            : "";

    var parentName =
        parentPath.Length > 0
            ? parentPath.Split('.').Last()
            : "";

    var optional =
        new Dictionary<string, object?>(
            StringComparer.Ordinal)
        {
            ["mobility"] =
                Text(
                    ReadMember(
                        export,
                        "Mobility")),
            ["affectsWorld"] =
                Boolean(
                    ReadMember(
                        export,
                        "bAffectsWorld")),
            ["indirectLightingIntensity"] =
                Number(
                    ReadMember(
                        export,
                        "IndirectLightingIntensity")),
            ["volumetricScatteringIntensity"] =
                Number(
                    ReadMember(
                        export,
                        "VolumetricScatteringIntensity")),
            ["specularScale"] =
                Number(
                    ReadMember(
                        export,
                        "SpecularScale")),
            ["castStaticShadows"] =
                Boolean(
                    ReadMember(
                        export,
                        "CastStaticShadows")),
            ["castDynamicShadows"] =
                Boolean(
                    ReadMember(
                        export,
                        "CastDynamicShadows")),
            ["affectTranslucentLighting"] =
                Boolean(
                    ReadMember(
                        export,
                        "bAffectTranslucentLighting")),
            ["lightFunctionMaterial"] =
                Text(
                    ReadMember(
                        export,
                        "LightFunctionMaterial"))
        };

    counts[kind] =
        counts.TryGetValue(
            kind,
            out var count)
            ? count + 1
            : 1;

    rows.Add(
        new {
            id =
                $"light_{rows.Count:000}",
            actorName = parentName,
            componentName = export.Name,
            componentType = kind,
            sourceType = fullType,
            sourcePath = actorPath,
            hierarchy,
            properties = new {
                intensity,
                lightColor,
                attenuationRadiusCm = radius,
                innerConeAngleDegrees = innerCone,
                outerConeAngleDegrees = outerCone,
                intensityUnits = units,
                useInverseSquaredFalloff =
                    inverseSquared,
                lightFalloffExponent =
                    falloffExponent,
                sourceRadiusCm = sourceRadius,
                softSourceRadiusCm =
                    softSourceRadius,
                sourceLengthCm = sourceLength,
                temperatureKelvin =
                    temperature,
                useTemperature,
                visible,
                castShadows,
                optional
            }
        });
}

var expected =
    new Dictionary<string, int> {
        ["point"] = 144,
        ["spot"] = 19,
        ["directional"] = 2,
        ["sky"] = 1
    };

if (
    rows.Count != 166 ||
    expected.Any(
        pair =>
            !counts.TryGetValue(
                pair.Key,
                out var value)
            || value != pair.Value))
{
    Console.Error.WriteLine(
        "Nacht light census mismatch "
        + JsonSerializer.Serialize(counts));
    return 4;
}

var output = new {
    schemaVersion = 1,
    sourcePackage = maps[0],
    coordinateSystem = new {
        source = "Unreal Engine centimeters",
        target = "XZIEL meters X,-Y,Z",
        hierarchyConvention =
            "component local transforms ordered child-to-parent"
    },
    lightCount = rows.Count,
    typeCounts = counts,
    lights = rows
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
    "XZIEL_NACHT_LIGHT_COMPONENTS_OK "
    + JsonSerializer.Serialize(
        new {
            output.lightCount,
            output.typeCounts
        }));

return 0;
