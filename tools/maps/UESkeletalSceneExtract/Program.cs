using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length != 6)
{
    Console.Error.WriteLine(
        "usage: UESkeletalSceneExtract <unpacked-root> <mappings.usmap> <class-census.json> <xzsk-report.json> <output.json> <source-game>");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var xzskReportPath = args[3];
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
using var xzskDoc = JsonDocument.Parse(File.ReadAllText(xzskReportPath));

var mapPackages = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Select(row =>
        NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("packagePath missing")))
    .Where(path => path.EndsWith(".umap", StringComparison.OrdinalIgnoreCase))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
    .ToArray();

var nativeMeshes = new Dictionary<string, NativeSkeletalMesh>(
    StringComparer.OrdinalIgnoreCase);

foreach (var row in xzskDoc.RootElement.GetProperty("meshes").EnumerateArray())
{
    var objectPath =
        row.GetProperty("objectPath").GetString()
        ?? throw new InvalidDataException("XZSK objectPath missing");
    var packagePath =
        row.GetProperty("packagePath").GetString()
        ?? throw new InvalidDataException("XZSK packagePath missing");
    var file =
        row.GetProperty("file").GetString()
        ?? throw new InvalidDataException("XZSK file missing");
    var skeletonHash =
        row.GetProperty("skeletonHash").GetString()
        ?? throw new InvalidDataException("XZSK skeletonHash missing");
    var index = row.GetProperty("index").GetInt32();

    if (!nativeMeshes.TryAdd(
            objectPath,
            new NativeSkeletalMesh(
                objectPath,
                packagePath,
                file,
                skeletonHash,
                index)))
    {
        throw new InvalidDataException(
            "duplicate XZSK objectPath: " + objectPath);
    }
}

if (mapPackages.Length == 0)
    throw new InvalidDataException("no .umap packages in source census");
if (nativeMeshes.Count != 3)
    throw new InvalidDataException(
        "expected exactly 3 recovered source skeletal meshes, got " +
        nativeMeshes.Count);

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

var rows = new List<object>();
var failures = new List<object>();
var unresolved = new List<object>();
var packagesLoaded = 0;
var allSkeletalComponents = 0;
var skeletalComponents = 0;
var embeddedSkeletalComponents = new List<object>();
var worldCache = new Dictionary<string, FTransform>(StringComparer.Ordinal);
var visiting = new HashSet<string>(StringComparer.Ordinal);

foreach (var logicalPackage in mapPackages)
{
    var resolved = ResolveProviderPackagePath(provider, logicalPackage);
    if (resolved is null)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        var exports = Enumerable
            .Range(0, package.ExportMapLength)
            .Select(index => package.GetExport(index))
            .ToArray();

        var components = exports
            .OfType<USceneComponent>()
            .Where(component =>
                component.ExportType.Contains(
                    "SkeletalMeshComponent",
                    StringComparison.OrdinalIgnoreCase))
            .OrderBy(component => component.GetPathName(), StringComparer.Ordinal)
            .ToArray();

        foreach (var component in components)
        {
            allSkeletalComponents++;
            try
            {
                var actor = FindOwningActor(component);
                if (actor is null)
                {
                    unresolved.Add(new {
                        packagePath = logicalPackage,
                        componentPath = component.GetPathName(),
                        reason = "owning actor unresolved"
                    });
                    continue;
                }

                if (!string.Equals(
                        actor.ExportType,
                        "SkeletalMeshActor",
                        StringComparison.Ordinal))
                {
                    embeddedSkeletalComponents.Add(new {
                        packagePath = logicalPackage,
                        actorObjectPath = actor.GetPathName(),
                        actorName = actor.Name,
                        actorClassName = actor.ExportType,
                        componentObjectPath = component.GetPathName(),
                        disposition = "embedded_skeletal_component_preserved_for_actor_adapter"
                    });
                }

                // FULL source authority includes standalone SkeletalMeshActor
                // components and Blueprint-owned skeletal components alike.
                // Keep the embedded classification as audit metadata, but
                // resolve every cooked component to its exact source XZSK.
                skeletalComponents++;

                var meshReference =
                    TryPackageIndex(component, "SkeletalMesh") ??
                    TryPackageIndex(component, "SkeletalMeshAsset") ??
                    TryPackageIndex(component, "SkinnedAsset");

                if (meshReference is null || meshReference.IsNull)
                {
                    unresolved.Add(new {
                        packagePath = logicalPackage,
                        actorObjectPath = actor.GetPathName(),
                        actorName = actor.Name,
                        actorClassName = actor.ExportType,
                        componentPath = component.GetPathName(),
                        attemptedProperties = new[] {
                            "SkeletalMesh",
                            "SkeletalMeshAsset",
                            "SkinnedAsset"
                        },
                        reason = "SkeletalMesh reference null"
                    });
                    continue;
                }

                var mesh = meshReference.Load<UObject>();
                if (mesh is null)
                {
                    unresolved.Add(new {
                        packagePath = logicalPackage,
                        actorObjectPath = actor.GetPathName(),
                        actorName = actor.Name,
                        actorClassName = actor.ExportType,
                        componentPath = component.GetPathName(),
                        dependencyIndex = meshReference.Index,
                        reason = "SkeletalMesh reference failed to load"
                    });
                    continue;
                }

                var meshPath = mesh.GetPathName();
                if (!nativeMeshes.TryGetValue(meshPath, out var nativeMesh))
                {
                    unresolved.Add(new {
                        packagePath = logicalPackage,
                        actorObjectPath = actor.GetPathName(),
                        actorName = actor.Name,
                        actorClassName = actor.ExportType,
                        componentPath = component.GetPathName(),
                        sourceMeshObjectPath = meshPath,
                        recoveredXzskObjectPaths = nativeMeshes.Keys
                            .OrderBy(value => value, StringComparer.OrdinalIgnoreCase)
                            .ToArray(),
                        reason = "loaded SkeletalMesh missing from XZSK report"
                    });
                    continue;
                }

                var world = ResolveWorldTransform(
                    component,
                    worldCache,
                    visiting);
                var matrix = ToXzielMatrix(world);
                if (!FiniteMatrix(matrix))
                    throw new InvalidDataException(
                        "non-finite skeletal component transform");

                rows.Add(new {
                    packagePath = logicalPackage,
                    actorObjectPath = actor.GetPathName(),
                    actorName = actor.Name,
                    actorClassName = actor.ExportType,
                    componentObjectPath = component.GetPathName(),
                    sourceSkeletalMeshObjectPath = nativeMesh.ObjectPath,
                    sourceSkeletalMeshPackagePath = nativeMesh.PackagePath,
                    sourceXzskFile = nativeMesh.File,
                    sourceXzskIndex = nativeMesh.Index,
                    skeletonHash = nativeMesh.SkeletonHash,
                    matrixRowMajor = matrix,
                    positionMeters = new[] {
                        matrix[3],
                        matrix[7],
                        matrix[11]
                    }
                });
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = logicalPackage,
                    componentPath = component.GetPathName(),
                    error = e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            resolvedPath = resolved,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var ordered = rows
    .OrderBy(row => JsonSerializer.Serialize(row), StringComparer.Ordinal)
    .ToArray();

var ready =
    packagesLoaded == mapPackages.Length &&
    failures.Count == 0 &&
    unresolved.Count == 0 &&
    allSkeletalComponents == 3 &&
    skeletalComponents == 3 &&
    embeddedSkeletalComponents.Count == 1 &&
    ordered.Length == 3 &&
    ordered
        .Select(row => JsonSerializer.Serialize(row))
        .Distinct(StringComparer.Ordinal)
        .Count() == 3;

var output = new {
    schemaVersion = 1,
    sourceGameName,
    mapPackageCount = mapPackages.Length,
    packagesLoaded,
    sourceRecoveredSkeletalMeshCount = nativeMeshes.Count,
    allSkeletalComponentCount = allSkeletalComponents,
    skeletalComponentCount = skeletalComponents,
    embeddedSkeletalComponentCount = embeddedSkeletalComponents.Count,
    embeddedSkeletalComponents,
    resolvedActorCount = ordered.Length,
    unresolvedCount = unresolved.Count,
    failureCount = failures.Count,
    coordinateSystem = new {
        source = "Unreal X,Y,Z centimeters",
        runtime = "XZIEL X,-Y,Z meters",
        matrixConvention = "row_major_column_vector_T_R_S",
        centimetersToMeters = 0.01
    },
    actors = ordered,
    unresolved,
    failures,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        output,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZOGOT_UE_SKELETAL_SCENE_EXTRACT " +
    JsonSerializer.Serialize(new {
        packagesLoaded,
        allSkeletalComponents,
        skeletalComponents,
        embeddedSkeletalComponents = embeddedSkeletalComponents.Count,
        resolved = ordered.Length,
        unresolved = unresolved.Count,
        failures = failures.Count,
        ready
    }));

foreach (var row in ordered)
    Console.WriteLine(
        "XZOGOT_UE_SKELETAL_ACTOR " +
        JsonSerializer.Serialize(row));

foreach (var row in unresolved)
    Console.WriteLine(
        "XZOGOT_UE_SKELETAL_UNRESOLVED " +
        JsonSerializer.Serialize(row));

if (!ready)
{
    Console.WriteLine("XZOGOT_UE_SKELETAL_SCENE_EXTRACT_FAILURE");
    return 5;
}

Console.WriteLine("XZOGOT_UE_SKELETAL_SCENE_EXTRACT_GREEN");
return 0;

static FPackageIndex? TryPackageIndex(UObject source, string property)
{
    try
    {
        return source.GetOrDefault<FPackageIndex>(property);
    }
    catch
    {
        return null;
    }
}

static UObject? FindOwningActor(UObject source)
{
    var outer = source.Outer;
    var guard = 0;

    while (outer is not null && guard++ < 64)
    {
        if (!outer.TryLoad(out var loaded) || loaded is null)
            return null;

        // Cooked Blueprint actor instances do not necessarily have an
        // ExportType ending in "Actor" (for example NewBlueprint1_2_C).
        // Scene components may be nested under other scene components, so walk
        // outward until the first non-scene-component UObject. That object is
        // the owning cooked actor instance and preserves Blueprint ownership.
        if (loaded is not USceneComponent)
            return loaded;

        outer = loaded.Outer;
    }

    return null;
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

            result[row * 4 + column] = checked((float)value);
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
    => matrix.Length == 16 && matrix.All(float.IsFinite);

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

    var shardNumber = normalized.AsSpan(6, slash - 6);
    for (var i = 0; i < shardNumber.Length; ++i)
        if (!char.IsDigit(shardNumber[i]))
            return normalized;

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

sealed record NativeSkeletalMesh(
    string ObjectPath,
    string PackagePath,
    string File,
    string SkeletonHash,
    int Index);
