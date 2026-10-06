using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Versions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UENuketownMaterialDependencies <unpacked-root> <mappings.usmap> <material-manifest.json> <xzml-report.json> <output.json>");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var manifestPath = args[2];
var xzmlPath = args[3];
var outputPath = args[4];

var manifest = JObject.Parse(File.ReadAllText(manifestPath));
var xzml = JObject.Parse(File.ReadAllText(xzmlPath));

var texturePaths = xzml["textureAssets"]?
    .Values<JObject>()
    .Select(x => x["sourcePath"]?.Value<string>() ?? "")
    .Where(x => !string.IsNullOrWhiteSpace(x))
    .ToArray() ?? Array.Empty<string>();

var textureBasenames = texturePaths
    .GroupBy(x => PackageBaseName(x), StringComparer.OrdinalIgnoreCase)
    .ToDictionary(g => g.Key, g => g.ToArray(), StringComparer.OrdinalIgnoreCase);

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    true,
    new VersionContainer(EGame.GAME_UE5_1))
{
    MappingsContainer = new FileUsmapTypeMappingsProvider(mappingsPath)
};
provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var materials = manifest["materials"]?.Values<JObject>().ToArray()
    ?? Array.Empty<JObject>();
var targets = materials.Where(IsDependencyTarget).ToArray();

var rows = new JArray();
var failures = new JArray();
var textureImportTotal = 0;
var uniqueTextureImportMaterials = 0;
var nameMapUniqueMaterials = 0;

foreach (var material in targets)
{
    var materialPath = material["materialPath"]?.Value<string>() ?? "";
    var packagePath = MaterialObjectPathToPackagePath(materialPath);
    var resolved = ResolveProviderPackagePath(provider, packagePath);
    if (resolved is null)
    {
        failures.Add(new JObject
        {
            ["materialPath"] = materialPath,
            ["packagePath"] = packagePath,
            ["error"] = "provider package unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        var textureImports = new JArray();
        var allImports = new JArray();

        if (package is Package legacy)
        {
            foreach (var import in legacy.ImportMap)
            {
                var row = new JObject
                {
                    ["classPackage"] = import.ClassPackage.Text,
                    ["className"] = import.ClassName.Text,
                    ["objectName"] = import.ObjectName.Text,
                    ["outerIndex"] = import.OuterIndex?.Index ?? 0,
                    ["resolvedOuter"] = import.OuterIndex?.ResolvedObject?.ToString()
                };
                allImports.Add(row);

                if (import.ClassName.Text.Contains(
                        "Texture",
                        StringComparison.OrdinalIgnoreCase))
                {
                    textureImports.Add(row.DeepClone());
                }
            }
        }

        textureImportTotal += textureImports.Count;
        if (textureImports.Count == 1)
            uniqueTextureImportMaterials++;

        var nameMapCandidates = new JArray();
        var seenCandidates = new HashSet<string>(
            StringComparer.OrdinalIgnoreCase);

        foreach (var entry in package.NameMap)
        {
            var name = entry.Name;
            if (string.IsNullOrWhiteSpace(name))
                continue;

            if (!textureBasenames.TryGetValue(name, out var exactPaths))
                continue;

            foreach (var texturePath in exactPaths)
            {
                if (seenCandidates.Add(texturePath))
                    nameMapCandidates.Add(texturePath);
            }
        }

        if (nameMapCandidates.Count == 1)
            nameMapUniqueMaterials++;

        rows.Add(new JObject
        {
            ["materialPath"] = materialPath,
            ["packagePath"] = packagePath,
            ["resolvedPackagePath"] = resolved,
            ["textureImportCount"] = textureImports.Count,
            ["textureImports"] = textureImports,
            ["nameMapTextureCandidateCount"] = nameMapCandidates.Count,
            ["nameMapTextureCandidates"] = nameMapCandidates,
            ["importCount"] = allImports.Count,
            ["imports"] = allImports
        });
    }
    catch (Exception e)
    {
        failures.Add(new JObject
        {
            ["materialPath"] = materialPath,
            ["packagePath"] = packagePath,
            ["resolvedPackagePath"] = resolved,
            ["error"] = e.GetType().FullName + ": " + e.Message
        });
    }
}

var output = new JObject
{
    ["schemaVersion"] = 1,
    ["targetMaterialCount"] = targets.Length,
    ["loadedMaterialCount"] = rows.Count,
    ["failureCount"] = failures.Count,
    ["textureImportTotal"] = textureImportTotal,
    ["uniqueTextureImportMaterials"] = uniqueTextureImportMaterials,
    ["nameMapUniqueMaterials"] = nameMapUniqueMaterials,
    ["materials"] = rows,
    ["failures"] = failures,
    ["ready"] = failures.Count == 0 && rows.Count == targets.Length
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(outputPath, output.ToString(Formatting.Indented));

Console.WriteLine(
    "XZOGOT_NUKETOWN_MATERIAL_DEPENDENCIES " +
    new JObject
    {
        ["targets"] = targets.Length,
        ["loaded"] = rows.Count,
        ["failures"] = failures.Count,
        ["textureImports"] = textureImportTotal,
        ["uniqueImportMaterials"] = uniqueTextureImportMaterials,
        ["uniqueNameMapMaterials"] = nameMapUniqueMaterials,
        ["ready"] = output["ready"]
    }.ToString(Formatting.None));

if (output["ready"]?.Value<bool>() != true)
{
    Console.WriteLine("XZOGOT_NUKETOWN_MATERIAL_DEPENDENCIES_FAILURE");
    return 5;
}

Console.WriteLine("XZOGOT_NUKETOWN_MATERIAL_DEPENDENCIES_GREEN");
return 0;

static bool IsDependencyTarget(JObject material)
{
    var canonical = material["canonicalTextures"] as JObject;
    var diffuse = canonical?["diffuse"]?.Value<string>() ?? "";
    if (!string.IsNullOrWhiteSpace(diffuse))
        return false;

    var textures = material["textures"]?.Values<JObject>().ToArray()
        ?? Array.Empty<JObject>();
    var srgb = textures
        .Where(x => x["native"]?["srgb"]?.Value<bool>() == true)
        .Select(x => x["texturePath"]?.Value<string>() ?? "")
        .Where(x => !string.IsNullOrWhiteSpace(x))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToArray();
    if (srgb.Length == 1)
        return false;

    var path = material["materialPath"]?.Value<string>() ?? "";
    return path.Contains("/nt/", StringComparison.OrdinalIgnoreCase);
}

static string MaterialObjectPathToPackagePath(string objectPath)
{
    var normalized = objectPath.Replace('\\', '/');
    var pavlov = normalized.IndexOf(
        "Pavlov/",
        StringComparison.OrdinalIgnoreCase);
    if (pavlov >= 0)
        normalized = normalized[pavlov..];

    var lastSlash = normalized.LastIndexOf('/');
    var lastDot = normalized.LastIndexOf('.');
    if (lastDot > lastSlash)
        normalized = normalized[..lastDot];

    return normalized + ".uasset";
}

static string PackageBaseName(string sourcePath)
{
    var normalized = sourcePath.Replace('\\', '/');
    var name = normalized[(normalized.LastIndexOf('/') + 1)..];
    var dot = name.IndexOf('.');
    if (dot >= 0)
        name = name[..dot];
    return name;
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    if (provider.TryGetGameFile(logicalPath, out _))
        return logicalPath;

    var normalized = logicalPath.Replace('\\', '/');
    return provider.Files.Keys.FirstOrDefault(
        key => key.EndsWith(
            normalized,
            StringComparison.OrdinalIgnoreCase));
}
