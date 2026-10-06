using System.Security.Cryptography;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Sound;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Sounds;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

if (args.Length < 5)
{
    Console.Error.WriteLine(
        "usage: UENuketownAudioExtract <unpacked-root> <mappings.usmap> <output-dir> <manifest.json> <package> [package...]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var outputDir = args[2];
var manifestPath = args[3];
var targets = args.Skip(4).ToArray();

if (!Directory.Exists(root))
    throw new DirectoryNotFoundException(root);
if (!File.Exists(mappingsPath))
    throw new FileNotFoundException("mappings missing", mappingsPath);

Directory.CreateDirectory(outputDir);

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

var rows = new JArray();
var failures = new JArray();

foreach (var logicalPath in targets)
{
    var resolved = ResolveProviderPackagePath(provider, logicalPath);
    if (resolved is null)
    {
        failures.Add(new JObject
        {
            ["packagePath"] = logicalPath,
            ["error"] = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        var decodedAny = false;

        for (var exportIndex = 0; exportIndex < package.ExportMapLength; exportIndex++)
        {
            var export = package.GetExport(exportIndex);
            if (export is not USoundWave sound)
                continue;

            sound.Decode(true, out var format, out var data);
            if (data is null || data.Length < 64 || string.IsNullOrWhiteSpace(format))
            {
                failures.Add(new JObject
                {
                    ["packagePath"] = logicalPath,
                    ["exportIndex"] = exportIndex,
                    ["exportName"] = export.Name,
                    ["error"] = "sound decode returned empty payload"
                });
                continue;
            }

            var safeName = new string(
                export.Name.Select(c => char.IsLetterOrDigit(c) || c is '_' or '-' ? c : '_').ToArray());
            var ext = format.Trim().ToLowerInvariant();
            var fileName = safeName + "." + ext;
            var outPath = Path.Combine(outputDir, fileName);
            File.WriteAllBytes(outPath, data);

            var sha = Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
            rows.Add(new JObject
            {
                ["packagePath"] = logicalPath,
                ["resolvedPackagePath"] = resolved,
                ["exportIndex"] = exportIndex,
                ["exportName"] = export.Name,
                ["format"] = format,
                ["bytes"] = data.Length,
                ["sha256"] = sha,
                ["fileName"] = fileName
            });
            decodedAny = true;
        }

        if (!decodedAny)
        {
            failures.Add(new JObject
            {
                ["packagePath"] = logicalPath,
                ["error"] = "no USoundWave decoded"
            });
        }
    }
    catch (Exception e)
    {
        failures.Add(new JObject
        {
            ["packagePath"] = logicalPath,
            ["error"] = e.GetType().FullName + ": " + e.Message
        });
    }
}

var ready = failures.Count == 0 && rows.Count == targets.Length;
var manifest = new JObject
{
    ["schemaVersion"] = 1,
    ["sourceGame"] = "ue5.1",
    ["requestedPackageCount"] = targets.Length,
    ["decodedSoundCount"] = rows.Count,
    ["sounds"] = rows,
    ["failures"] = failures,
    ["ready"] = ready
};

Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(manifestPath))!);
File.WriteAllText(manifestPath, manifest.ToString(Formatting.Indented));

Console.WriteLine(
    "XZOGOT_NUKETOWN_AUDIO_EXTRACT " +
    new JObject
    {
        ["requested"] = targets.Length,
        ["decoded"] = rows.Count,
        ["failures"] = failures.Count,
        ["ready"] = ready
    }.ToString(Formatting.None));

if (!ready)
{
    Console.WriteLine("XZOGOT_NUKETOWN_AUDIO_EXTRACT_FAILURE");
    return 5;
}

Console.WriteLine("XZOGOT_NUKETOWN_AUDIO_EXTRACT_GREEN");
return 0;

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    if (provider.TryGetGameFile(logicalPath, out _))
        return logicalPath;

    var normalized = logicalPath.Replace('\\', '/');
    return provider.Files.Keys.FirstOrDefault(
        key => key.EndsWith(normalized, StringComparison.OrdinalIgnoreCase));
}
