using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using System.Collections;
using System.Globalization;
using System.Reflection;
using System.Text.Json;

if (args.Length != 2)
{
    Console.Error.WriteLine(
        "usage: NachtPostProcessExtractor <unpacked-root> <output-json>");
    return 2;
}

const BindingFlags Flags =
    BindingFlags.Instance |
    BindingFlags.Public |
    BindingFlags.NonPublic;

object? Read(object target, string name)
{
    var field = target.GetType().GetField(name, Flags);
    if (field is not null)
    {
        try { return field.GetValue(target); }
        catch { }
    }

    var property = target.GetType().GetProperty(name, Flags);
    if (property is not null &&
        property.GetIndexParameters().Length == 0 &&
        property.GetMethod is not null)
    {
        try { return property.GetValue(target); }
        catch { }
    }

    return null;
}

string Text(object? value)
{
    if (value is null)
        return "";
    try { return value.ToString() ?? ""; }
    catch { return ""; }
}

bool IsInterestingName(string name)
{
    var probes = new[] {
        "Exposure",
        "AutoExposure",
        "EyeAdaptation",
        "Film",
        "Tone",
        "Color",
        "WhiteTemp",
        "WhiteTint",
        "Saturation",
        "Contrast",
        "Gamma",
        "Gain",
        "Offset",
        "Bloom",
        "Vignette",
        "AmbientCubemap",
        "IndirectLighting",
        "SceneColorTint",
        "PostProcess",
        "Settings",
        "BlendWeight",
        "Priority",
        "Unbound"
    };

    return probes.Any(
        probe => name.Contains(
            probe,
            StringComparison.OrdinalIgnoreCase));
}

Dictionary<string, object?> FlattenSimple(
    object? value,
    int depth = 0,
    string prefix = "")
{
    var result =
        new Dictionary<string, object?>(
            StringComparer.Ordinal);

    if (value is null || depth > 3)
        return result;

    var type = value.GetType();

    if (value is string ||
        value is bool ||
        value is byte ||
        value is sbyte ||
        value is short ||
        value is ushort ||
        value is int ||
        value is uint ||
        value is long ||
        value is ulong ||
        value is float ||
        value is double ||
        value is decimal ||
        type.IsEnum)
    {
        result[prefix] = value.ToString();
        return result;
    }

    if (value is IEnumerable enumerable &&
        value is not string)
    {
        var index = 0;
        foreach (var item in enumerable)
        {
            if (index >= 128)
                break;

            var childPrefix =
                string.IsNullOrEmpty(prefix)
                    ? $"[{index}]"
                    : $"{prefix}[{index}]";

            foreach (var pair in
                FlattenSimple(
                    item,
                    depth + 1,
                    childPrefix))
            {
                result[pair.Key] = pair.Value;
            }

            index++;
        }

        return result;
    }

    foreach (var field in
        type.GetFields(Flags))
    {
        object? child = null;
        try { child = field.GetValue(value); }
        catch { continue; }

        var childName =
            string.IsNullOrEmpty(prefix)
                ? field.Name
                : $"{prefix}.{field.Name}";

        if (IsInterestingName(field.Name) ||
            depth < 2)
        {
            foreach (var pair in
                FlattenSimple(
                    child,
                    depth + 1,
                    childName))
            {
                result[pair.Key] = pair.Value;
            }
        }
    }

    foreach (var property in
        type.GetProperties(Flags))
    {
        if (property.GetIndexParameters().Length != 0 ||
            property.GetMethod is null)
            continue;

        object? child = null;
        try { child = property.GetValue(value); }
        catch { continue; }

        var childName =
            string.IsNullOrEmpty(prefix)
                ? property.Name
                : $"{prefix}.{property.Name}";

        if (IsInterestingName(property.Name) ||
            depth < 2)
        {
            foreach (var pair in
                FlattenSimple(
                    child,
                    depth + 1,
                    childName))
            {
                result[pair.Key] = pair.Value;
            }
        }
    }

    return result;
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
            file =>
                Path.GetFileName(file.Path).Equals(
                    "Nacht_de_Untoten.umap",
                    StringComparison.OrdinalIgnoreCase))
        .Select(file => file.Path)
        .Distinct(
            StringComparer.OrdinalIgnoreCase)
        .ToArray();

if (maps.Length != 1)
{
    Console.Error.WriteLine(
        $"expected exactly one Nacht_de_Untoten.umap, got {maps.Length}");
    return 3;
}

var exports =
    provider.LoadPackage(maps[0])
        .GetExports()
        .ToArray();

var rows = new List<object>();

foreach (var export in exports)
{
    var fullType =
        export.GetType().FullName ??
        export.GetType().Name;
    var path =
        export.GetPathName() ?? "";

    var candidate =
        fullType.Contains(
            "PostProcess",
            StringComparison.OrdinalIgnoreCase)
        || fullType.Contains(
            "WorldSettings",
            StringComparison.OrdinalIgnoreCase)
        || path.Contains(
            "PostProcess",
            StringComparison.OrdinalIgnoreCase);

    if (!candidate)
        continue;

    var tags =
        new SortedDictionary<string, string>(
            StringComparer.OrdinalIgnoreCase);

    var properties = Read(export, "Properties");
    if (properties is IEnumerable enumerable)
    {
        foreach (var tag in enumerable)
        {
            if (tag is null)
                continue;

            var name =
                Text(Read(tag, "Name"));
            if (string.IsNullOrWhiteSpace(name))
                continue;

            if (!IsInterestingName(name) &&
                !name.Equals(
                    "Settings",
                    StringComparison.OrdinalIgnoreCase))
                continue;

            var tagValue =
                Text(Read(tag, "Tag"));
            tags[name] = tagValue;
        }
    }

    var settings =
        Read(export, "Settings")
        ?? Read(export, "PostProcessSettings");

    rows.Add(
        new {
            exportName =
                export.Name.ToString(),
            sourceType = fullType,
            sourcePath = path,
            tags,
            resolvedMembers =
                FlattenSimple(
                    settings,
                    0,
                    "Settings")
        });
}

var report = new {
    schemaVersion = 1,
    sourcePackage = maps[0],
    exportCount = exports.Length,
    candidateCount = rows.Count,
    candidates = rows
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
    "XZIEL_NACHT_POSTPROCESS_CENSUS_OK " +
    JsonSerializer.Serialize(
        new {
            report.exportCount,
            report.candidateCount
        }));

return rows.Count > 0 ? 0 : 4;
