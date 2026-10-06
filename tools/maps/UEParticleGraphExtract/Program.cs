using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Collections;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEParticleGraphExtract <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
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
        _ => throw new ArgumentException("unsupported source-game: " + sourceGameName)
    };

string NormalizeMergedShardPath(string value)
{
    var path = value.Replace('\\', '/');
    return Regex.Replace(path, @"^shard-\d+/", "", RegexOptions.IgnoreCase);
}

string? ResolveProviderPackagePath(DefaultFileProvider provider, string logicalPath)
{
    var normalized = NormalizeMergedShardPath(logicalPath);
    foreach (var file in provider.Files.Values)
    {
        var candidate = file.Path.Replace('\\', '/');
        if (candidate.Equals(normalized, StringComparison.OrdinalIgnoreCase) ||
            candidate.EndsWith("/" + normalized, StringComparison.OrdinalIgnoreCase))
            return file.Path;
    }
    return null;
}

var scriptStructCount = 0;
var scriptStructExpandedCount = 0;
var scriptStructOpaqueCount = 0;

bool IsReflectableSourceValue(object? value)
{
    if (value is null) return false;
    var fullName = value.GetType().FullName ?? "";
    return fullName.StartsWith(
        "CUE4Parse.UE4.Objects.",
        StringComparison.Ordinal);
}

object? DescribeReflectedSourceValue(object value, int depth)
{
    if (depth >= 6)
        return new {
            kind = value.GetType().FullName,
            truncated = true,
            text = value.ToString()
        };

    var flags =
        System.Reflection.BindingFlags.Instance |
        System.Reflection.BindingFlags.Public;
    var members = new SortedDictionary<string, object?>(
        StringComparer.Ordinal);
    var skip = new HashSet<string>(
        new[] {
            "Owner", "Outer", "Package", "Provider", "ResolvedObject",
            "Class", "Super", "Template", "Archetype"
        },
        StringComparer.OrdinalIgnoreCase);

    foreach (var field in value.GetType()
                 .GetFields(flags)
                 .OrderBy(x => x.Name, StringComparer.Ordinal))
    {
        if (field.IsStatic || skip.Contains(field.Name))
            continue;
        if (members.Count >= 96) break;
        try
        {
            members[field.Name] = DescribeValue(
                field.GetValue(value),
                depth + 1);
        }
        catch
        {
        }
    }

    foreach (var property in value.GetType()
                 .GetProperties(flags)
                 .OrderBy(x => x.Name, StringComparer.Ordinal))
    {
        if (!property.CanRead ||
            property.GetIndexParameters().Length != 0 ||
            skip.Contains(property.Name) ||
            members.ContainsKey(property.Name))
            continue;
        if (members.Count >= 96) break;
        try
        {
            members[property.Name] = DescribeValue(
                property.GetValue(value),
                depth + 1);
        }
        catch
        {
        }
    }

    return new {
        kind = value.GetType().FullName,
        members
    };
}

object? DescribeValue(object? value, int depth = 0)
{
    if (value is null) return null;
    if (depth >= 6) return value.ToString();

    if (value is FPackageIndex index)
    {
        return new {
            kind = "FPackageIndex",
            index = index.Index,
            path = index.IsNull ? null :
                index.ResolvedObject?.GetPathName() ?? index.Name
        };
    }

    if (value is FScriptStruct scriptStruct)
    {
        scriptStructCount++;
        var payload = scriptStruct.StructType;
        var expandable =
            payload is FStructFallback ||
            IsReflectableSourceValue(payload);
        if (expandable)
            scriptStructExpandedCount++;
        else
            scriptStructOpaqueCount++;

        return new {
            kind = "FScriptStruct",
            structType = payload?.GetType().FullName,
            expanded = expandable,
            value = DescribeValue(payload, depth + 1)
        };
    }

    if (value is FStructFallback fallback)
    {
        return new {
            kind = "FStructFallback",
            properties = fallback.Properties
                .OrderBy(p => p.Name.Text, StringComparer.Ordinal)
                .Select(p => new {
                    name = p.Name.Text,
                    valueType = p.Tag?.GenericValue?.GetType().FullName,
                    value = DescribeValue(p.Tag?.GenericValue, depth + 1)
                }).ToArray()
        };
    }

    if (value is string || value is bool || value is Enum ||
        value is byte || value is sbyte || value is short || value is ushort ||
        value is int || value is uint || value is long || value is ulong ||
        value is float || value is double || value is decimal)
        return value;

    if (value is IEnumerable enumerable && value is not string)
    {
        var rows = new List<object?>();
        foreach (var item in enumerable)
        {
            if (rows.Count >= 2048) break;
            rows.Add(DescribeValue(item, depth + 1));
        }
        return rows.ToArray();
    }

    if (IsReflectableSourceValue(value))
        return DescribeReflectedSourceValue(value, depth);

    return new {
        kind = value.GetType().FullName,
        text = value.ToString()
    };
}

void CollectRefs(object? value, SortedSet<string> refs, int depth = 0)
{
    if (value is null || depth >= 8) return;

    if (value is FPackageIndex index)
    {
        if (!index.IsNull)
        {
            var path = index.ResolvedObject?.GetPathName() ?? index.Name;
            if (!string.IsNullOrWhiteSpace(path))
                refs.Add(path);
        }
        return;
    }

    if (value is FScriptStruct scriptStruct)
    {
        CollectRefs(scriptStruct.StructType, refs, depth + 1);
        return;
    }

    if (value is FStructFallback fallback)
    {
        foreach (var p in fallback.Properties)
            CollectRefs(p.Tag?.GenericValue, refs, depth + 1);
        return;
    }

    if (value is IEnumerable enumerable && value is not string)
    {
        foreach (var item in enumerable)
            CollectRefs(item, refs, depth + 1);
    }
}

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
var candidates = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Where(row => {
        if (!row.TryGetProperty("classes", out var classes)) return false;
        return classes.TryGetProperty("ParticleSystem", out var count) &&
            count.GetInt32() > 0;
    })
    .Select(row => NormalizeMergedShardPath(
        row.GetProperty("packagePath").GetString()
        ?? throw new InvalidDataException("packagePath missing")))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
    .ToArray();

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    new VersionContainer(sourceGame),
    StringComparer.OrdinalIgnoreCase)
{
    MappingsContainer = new FileUsmapTypeMappingsProvider(mappingsPath)
};
provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var packageFailures = new List<object>();
var systems = new List<object>();
var nodeTypeCounts = new SortedDictionary<string,int>(StringComparer.Ordinal);
var packagesLoaded = 0;
var totalNodes = 0;
var totalReferences = 0;
var distributionNodeCount = 0;

foreach (var logical in candidates)
{
    var resolved = ResolveProviderPackagePath(provider, logical);
    if (resolved is null)
    {
        packageFailures.Add(new { packagePath = logical, error = "provider path unresolved" });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        var exports = package.GetExports().ToArray();
        var particleExports = exports
            .Where(x =>
                x.ExportType.Equals("ParticleSystem", StringComparison.Ordinal) ||
                x.ExportType.StartsWith("ParticleEmitter", StringComparison.Ordinal) ||
                x.ExportType.StartsWith("ParticleModule", StringComparison.Ordinal) ||
                x.ExportType.Contains("ParticleLOD", StringComparison.Ordinal) ||
                x.ExportType.StartsWith("Distribution", StringComparison.Ordinal))
            .OrderBy(x => x.GetPathName(), StringComparer.Ordinal)
            .ToArray();

        foreach (var system in particleExports.Where(x =>
                     x.ExportType.Equals("ParticleSystem", StringComparison.Ordinal)))
        {
            var prefix = system.GetPathName() + ":";
            var nodes = particleExports
                .Where(x =>
                    x == system ||
                    x.GetPathName().StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                .ToArray();

            var nodeRows = new List<object>();
            var graphRefs = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var node in nodes)
            {
                var refs = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (var p in node.Properties)
                    CollectRefs(p.Tag?.GenericValue, refs);

                foreach (var reference in refs)
                    graphRefs.Add(reference);

                nodeTypeCounts[node.ExportType] =
                    nodeTypeCounts.GetValueOrDefault(node.ExportType) + 1;
                if (node.ExportType.StartsWith("Distribution", StringComparison.Ordinal))
                    distributionNodeCount++;
                totalNodes++;
                totalReferences += refs.Count;

                nodeRows.Add(new {
                    objectPath = node.GetPathName(),
                    exportType = node.ExportType,
                    references = refs.ToArray(),
                    properties = node.Properties
                        .OrderBy(p => p.Name.Text, StringComparer.Ordinal)
                        .Select(p => new {
                            name = p.Name.Text,
                            valueType = p.Tag?.GenericValue?.GetType().FullName,
                            value = DescribeValue(p.Tag?.GenericValue)
                        }).ToArray()
                });
            }

            systems.Add(new {
                packagePath = logical,
                objectPath = system.GetPathName(),
                exportType = system.ExportType,
                nodeCount = nodeRows.Count,
                referenceCount = graphRefs.Count,
                references = graphRefs.ToArray(),
                nodes = nodeRows
            });
        }
    }
    catch (Exception ex)
    {
        packageFailures.Add(new {
            packagePath = logical,
            error = ex.GetType().Name + ": " + ex.Message
        });
    }
}

var ready =
    candidates.Length > 0 &&
    packagesLoaded == candidates.Length &&
    packageFailures.Count == 0 &&
    systems.Count > 0;

var output = new {
    schemaVersion = 1,
    sourceGame = sourceGameName,
    candidatePackageCount = candidates.Length,
    packagesLoaded,
    particleSystemCount = systems.Count,
    totalNodes,
    totalReferences,
    distributionNodeCount,
    scriptStructCount,
    scriptStructExpandedCount,
    scriptStructOpaqueCount,
    nodeTypeCounts,
    systems,
    packageFailures,
    ready
};

Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(output, new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine("XZIEL_UE_PARTICLE_GRAPH " + JsonSerializer.Serialize(new {
    output.candidatePackageCount,
    output.packagesLoaded,
    output.particleSystemCount,
    output.totalNodes,
    output.totalReferences,
    output.scriptStructCount,
    output.scriptStructExpandedCount,
    output.scriptStructOpaqueCount,
    output.nodeTypeCounts,
    failureCount = packageFailures.Count,
    output.ready
}));

foreach (var failure in packageFailures.Take(20))
    Console.WriteLine("XZIEL_UE_PARTICLE_GRAPH_PACKAGE_FAILURE " + JsonSerializer.Serialize(failure));

if (!ready)
{
    Console.WriteLine("XZIEL_UE_PARTICLE_GRAPH_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_PARTICLE_GRAPH_GREEN");
return 0;
