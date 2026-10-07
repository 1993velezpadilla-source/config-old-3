using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Engine;
using CUE4Parse.UE4.Objects.Engine;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEParticleSceneExtract <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
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

string NormalizeMergedShardPath(string value)
{
    var path = value.Replace('\\', '/');
    return Regex.Replace(
        path,
        @"^shard-\d+/",
        "",
        RegexOptions.IgnoreCase);
}

string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
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

string? ReferencePath(FPackageIndex index)
{
    if (index.IsNull)
        return null;
    return index.ResolvedObject?.GetPathName() ?? index.Name;
}

bool HasSerializedProperty(UObject source, string name) =>
    source.Properties.Any(property =>
        property.Name.Text.Equals(name, StringComparison.Ordinal));

T InheritedValue<T>(
    UParticleSystemComponent instance,
    UParticleSystemComponent? authority,
    string name,
    T fallback)
{
    if (HasSerializedProperty(instance, name))
        return instance.GetOrDefault<T>(name, fallback);
    if (authority is not null && HasSerializedProperty(authority, name))
        return authority.GetOrDefault<T>(name, fallback);
    return fallback;
}

List<object> BuildHierarchy(
    USceneComponent start,
    UParticleSystemComponent? startAuthority)
{
    var rows = new List<object>();
    var seen = new HashSet<string>(StringComparer.Ordinal);
    USceneComponent? current = start;

    for (var depth = 0; current is not null && depth < 64; ++depth)
    {
        var path = current.GetPathName();
        if (!seen.Add(path))
            throw new InvalidOperationException("particle component attachment cycle: " + path);

        // Cooked map instances omit Blueprint component-template values when
        // they are unchanged. CUE4Parse's convenience getters then return the
        // native identity/default, which is not the authored Blueprint value.
        // For the particle component itself, inherit every omitted local
        // transform channel from the resolved component template.
        var authority = depth == 0 ? startAuthority : null;
        var locationFromTemplate =
            authority is not null &&
            !HasSerializedProperty(current, "RelativeLocation") &&
            HasSerializedProperty(authority, "RelativeLocation");
        var rotationFromTemplate =
            authority is not null &&
            !HasSerializedProperty(current, "RelativeRotation") &&
            HasSerializedProperty(authority, "RelativeRotation");
        var scaleFromTemplate =
            authority is not null &&
            !HasSerializedProperty(current, "RelativeScale3D") &&
            HasSerializedProperty(authority, "RelativeScale3D");

        var location = locationFromTemplate
            ? authority!.GetRelativeLocation()
            : current.GetRelativeLocation();
        var rotation = rotationFromTemplate
            ? authority!.GetRelativeRotation()
            : current.GetRelativeRotation();
        var scale = scaleFromTemplate
            ? authority!.GetRelativeScale3D()
            : current.GetRelativeScale3D();

        rows.Add(new
        {
            depth,
            objectPath = path,
            componentName = current.Name,
            locationUEcm = new { X = location.X, Y = location.Y, Z = location.Z },
            rotationUE = new { Pitch = rotation.Pitch, Yaw = rotation.Yaw, Roll = rotation.Roll },
            scale = new { X = scale.X, Y = scale.Y, Z = scale.Z },
            transformProvenance = new
            {
                location = locationFromTemplate ? "component_template" : "instance_or_native_default",
                rotation = rotationFromTemplate ? "component_template" : "instance_or_native_default",
                scale = scaleFromTemplate ? "component_template" : "instance_or_native_default"
            }
        });

        USceneComponent? parent = null;
        try
        {
            var attach = current.AttachParent;
            if (attach is { IsNull: false })
                attach.TryLoad<USceneComponent>(out parent);
        }
        catch
        {
            parent = null;
        }
        current = parent;
    }

    if (rows.Count == 0)
        throw new InvalidOperationException("empty particle hierarchy");

    return rows;
}



bool ComponentAuthorityNameMatches(string authorityName, string instanceName)
{
    if (authorityName.Equals(instanceName, StringComparison.OrdinalIgnoreCase))
        return true;

    const string suffix = "_GEN_VARIABLE";
    if (authorityName.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
    {
        var baseName = authorityName[..^suffix.Length];
        if (baseName.Equals(instanceName, StringComparison.OrdinalIgnoreCase))
            return true;
    }

    return false;
}

UBlueprintGeneratedClass? ResolveGeneratedClassByResolvedClassPath(
    DefaultFileProvider provider,
    string? classPath,
    string actorExportType)
{
    if (string.IsNullOrWhiteSpace(classPath))
        return null;

    var normalized = classPath!.Replace('\\', '/');
    var objectDot = normalized.LastIndexOf('.');
    var assetObjectPath =
        objectDot > 0 ? normalized[..objectDot] : normalized;

    string logicalAssetPath;
    if (assetObjectPath.StartsWith("/Game/", StringComparison.OrdinalIgnoreCase))
        logicalAssetPath = "Content/" + assetObjectPath[6..] + ".uasset";
    else if (assetObjectPath.StartsWith("Game/", StringComparison.OrdinalIgnoreCase))
        logicalAssetPath = "Content/" + assetObjectPath[5..] + ".uasset";
    else
        logicalAssetPath = assetObjectPath.TrimStart('/') + ".uasset";

    var providerPath = ResolveProviderPackagePath(provider, logicalAssetPath);
    if (providerPath is null)
        return null;

    try
    {
        var package = provider.LoadPackage(providerPath);
        return package.GetExports()
            .OfType<UBlueprintGeneratedClass>()
            .FirstOrDefault(x =>
                x.Name.Equals(actorExportType, StringComparison.OrdinalIgnoreCase));
    }
    catch
    {
        return null;
    }
}

UBlueprintGeneratedClass? ResolveBlueprintSuperClass(
    DefaultFileProvider provider,
    UBlueprintGeneratedClass current)
{
    string? superPath = null;
    string? superName = null;

    // UE4 serializes Blueprint class inheritance on UStruct.SuperStruct.
    // In cooked packages UObject.Super can be empty even when SuperStruct
    // points at a BlueprintGeneratedClass in another package.
    try
    {
        var superStruct = current.SuperStruct;
        if (!superStruct.IsNull)
        {
            if (superStruct.TryLoad<UBlueprintGeneratedClass>(out var loaded) &&
                loaded is not null)
                return loaded;

            superPath = superStruct.ResolvedObject?.GetPathName();
            superName = superStruct.ResolvedObject?.Name.Text
                ?? superStruct.Name;
        }
    }
    catch { }

    if (string.IsNullOrWhiteSpace(superName))
    {
        try
        {
            if (current.Super?.Object?.Value is UBlueprintGeneratedClass loaded)
                return loaded;

            superPath ??= current.Super?.GetPathName();
            superName ??= current.Super?.Name.Text;
        }
        catch { }
    }

    if (string.IsNullOrWhiteSpace(superName) ||
        !superName.EndsWith("_C", StringComparison.Ordinal))
        return null;

    return ResolveGeneratedClassByResolvedClassPath(
        provider,
        superPath,
        superName);
}

UBlueprintGeneratedClass? ResolveGeneratedClassByExportType(
    DefaultFileProvider provider,
    string actorExportType)
{
    if (string.IsNullOrWhiteSpace(actorExportType) ||
        !actorExportType.EndsWith("_C", StringComparison.Ordinal))
        return null;

    var assetFile = actorExportType[..^2] + ".uasset";
    foreach (var file in provider.Files.Values
                 .Where(file => {
                     var p = file.Path.Replace('\\', '/');
                     return p.EndsWith("/" + assetFile, StringComparison.OrdinalIgnoreCase) ||
                            p.Equals(assetFile, StringComparison.OrdinalIgnoreCase);
                 })
                 .OrderBy(file => file.Path, StringComparer.OrdinalIgnoreCase))
    {
        try
        {
            var package = provider.LoadPackage(file.Path);
            var generated = package.GetExports()
                .OfType<UBlueprintGeneratedClass>()
                .FirstOrDefault(x =>
                    x.Name.Equals(actorExportType, StringComparison.OrdinalIgnoreCase));
            if (generated is not null)
                return generated;
        }
        catch
        {
            // Try another package with the same asset basename.
        }
    }

    return null;
}

(UParticleSystemComponent? component, string? provenance)
ResolveCookedParticleComponentExport(
    DefaultFileProvider provider,
    UBlueprintGeneratedClass generated,
    string instanceName)
{
    string path;
    try
    {
        path = generated.GetPathName().Replace('\\', '/');
    }
    catch
    {
        return (null, null);
    }

    var objectDot = path.LastIndexOf('.');
    var assetPath = objectDot > 0 ? path[..objectDot] : path;

    string logicalAssetPath;
    if (assetPath.StartsWith("/Game/", StringComparison.OrdinalIgnoreCase))
        logicalAssetPath = "Content/" + assetPath[6..] + ".uasset";
    else if (assetPath.StartsWith("Game/", StringComparison.OrdinalIgnoreCase))
        logicalAssetPath = "Content/" + assetPath[5..] + ".uasset";
    else if (assetPath.StartsWith("Content/", StringComparison.OrdinalIgnoreCase))
        logicalAssetPath = assetPath + ".uasset";
    else
        logicalAssetPath = assetPath.TrimStart('/') + ".uasset";

    var providerPath = ResolveProviderPackagePath(provider, logicalAssetPath);
    if (providerPath is null)
        return (null, null);

    try
    {
        var package = provider.LoadPackage(providerPath);
        foreach (var candidate in package.GetExports()
                     .OfType<UParticleSystemComponent>()
                     .OrderBy(x => x.GetPathName(), StringComparer.Ordinal))
        {
            if (!ComponentAuthorityNameMatches(candidate.Name, instanceName))
                continue;

            return (
                candidate,
                "cooked_package_component_export:" +
                candidate.GetPathName());
        }
    }
    catch
    {
        // Cooked package may be partial. Continue to SCS/handler authorities.
    }

    return (null, null);
}

FPackageIndex? ReadParticleTemplateIndex(UParticleSystemComponent candidate)
{
    try
    {
        var index = candidate.GetOrDefault<FPackageIndex?>("Template");
        return index is { IsNull: false } ? index : null;
    }
    catch
    {
        return null;
    }
}

(UParticleSystemComponent? component, string? provenance)
ResolveBlueprintParticleComponentAuthority(
    DefaultFileProvider provider,
    UParticleSystemComponent component)
{
    UObject? owner = null;
    try
    {
        owner = component.Outer?.Object?.Value;
    }
    catch
    {
        owner = null;
    }

    if (owner is null ||
        !owner.ExportType.EndsWith("_C", StringComparison.Ordinal))
        return (null, null);

    string? resolvedClassPath = null;
    try
    {
        resolvedClassPath = owner.Class?.GetPathName();
    }
    catch { }

    var generated = ResolveGeneratedClassByResolvedClassPath(
        provider,
        resolvedClassPath,
        owner.ExportType);

    if (generated is null)
        generated = ResolveGeneratedClassByExportType(provider, owner.ExportType);

    if (generated is null)
        return (null, null);

    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    for (var current = generated;
         current is not null && seen.Add(current.GetPathName());
         current = ResolveBlueprintSuperClass(provider, current))
    {
        var cookedExport = ResolveCookedParticleComponentExport(
            provider,
            current,
            component.Name);
        if (cookedExport.component is not null)
            return cookedExport;

        foreach (var templateRef in current.ComponentTemplates)
        {
            try
            {
                if (templateRef is not { IsNull: false } ||
                    !templateRef.TryLoad<UParticleSystemComponent>(out var template) ||
                    template is null ||
                    !ComponentAuthorityNameMatches(template.Name, component.Name))
                    continue;

                return (
                    template,
                    "generated_class_component_template:" + template.GetPathName());
            }
            catch { }
        }

        try
        {
            if (current.SimpleConstructionScript is { IsNull: false } scsRef &&
                scsRef.TryLoad<USimpleConstructionScript>(out var scs) &&
                scs is not null)
            {
                foreach (var node in scs.GetAllNodesRecursive())
                {
                    if (!ComponentAuthorityNameMatches(
                            node.InternalVariableName.Text,
                            component.Name))
                        continue;

                    var template = node.GetComponentTemplate() as UParticleSystemComponent;
                    if (template is null)
                        continue;

                    return (
                        template,
                        "scs_component_template:" + template.GetPathName());
                }
            }
        }
        catch { }

        try
        {
            if (current.InheritableComponentHandler is { IsNull: false } handlerRef &&
                handlerRef.TryLoad<UInheritableComponentHandler>(out var handler) &&
                handler is not null)
            {
                foreach (var record in handler.GetRecords())
                {
                    if (!ComponentAuthorityNameMatches(
                            record.ComponentKey.SCSVariableName.Text,
                            component.Name))
                        continue;

                    if (record.ComponentTemplate is not { IsNull: false } templateRef ||
                        !templateRef.TryLoad<UParticleSystemComponent>(out var template) ||
                        template is null)
                        continue;

                    return (
                        template,
                        "inheritable_component_template:" + template.GetPathName());
                }
            }
        }
        catch { }
    }

    return (null, null);
}

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
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

if (mapPackages.Length == 0)
    throw new InvalidDataException("no .umap packages in source census");

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
var packageFailures = new List<object>();
var componentFailures = new List<object>();
var packagesLoaded = 0;
var referencedTemplateCount = 0;
var loadedTemplateCount = 0;
var nullTemplateCount = 0;
var templateTypeCounts = new SortedDictionary<string, int>(StringComparer.Ordinal);

foreach (var logicalPackage in mapPackages)
{
    var resolved = ResolveProviderPackagePath(provider, logicalPackage);
    if (resolved is null)
    {
        packageFailures.Add(new { packagePath = logicalPackage, error = "provider path unresolved" });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        foreach (var component in package.GetExports()
                     .OfType<UParticleSystemComponent>()
                     .OrderBy(x => x.GetPathName(), StringComparer.Ordinal))
        {
            try
            {
            var componentAuthority =
                ResolveBlueprintParticleComponentAuthority(provider, component);
            var authorityComponent = componentAuthority.component;

            FPackageIndex? templateIndex = ReadParticleTemplateIndex(component);
            string? templateProvenance = templateIndex is { IsNull: false }
                ? "instance:property"
                : null;

            if (templateIndex is null && authorityComponent is not null)
            {
                templateIndex = ReadParticleTemplateIndex(authorityComponent);
                if (templateIndex is { IsNull: false })
                    templateProvenance =
                        componentAuthority.provenance + ":Template";
            }

            string? templatePath = null;
            string? templateType = null;
            var templateLoaded = false;

            if (templateIndex is { IsNull: false })
            {
                referencedTemplateCount++;
                templatePath = ReferencePath(templateIndex);
                try
                {
                    var loaded = templateIndex.Load<UParticleSystem>();
                    if (loaded is not null)
                    {
                        templateLoaded = true;
                        loadedTemplateCount++;
                        templatePath = loaded.GetPathName();
                        templateType = loaded.ExportType;
                    }
                }
                catch
                {
                    // Preserve the exact FPackageIndex reference even when loading
                    // fails because cooked virtual namespaces do not mount it.
                }
            }
            else
            {
                nullTemplateCount++;
            }

            var typeKey =
                !string.IsNullOrWhiteSpace(templateType)
                    ? templateType!
                    : templatePath is null
                        ? "null"
                        : "unloaded_reference";
            templateTypeCounts[typeKey] =
                templateTypeCounts.GetValueOrDefault(typeKey) + 1;

            var componentPath = component.GetPathName();
            var lastDot = componentPath.LastIndexOf('.');
            var parentPath = lastDot > 0 ? componentPath[..lastDot] : "";
            var parentName =
                parentPath.Length > 0
                    ? parentPath.Split('.').Last()
                    : "";

            string? ownerExportType = null;
            string? ownerClassPath = null;
            try
            {
                var owner = component.Outer?.Object?.Value;
                ownerExportType = owner?.ExportType;
                ownerClassPath = owner?.Class?.GetPathName();
            }
            catch { }

            bool? explicitVisible = null;
            if (HasSerializedProperty(component, "bVisible"))
                explicitVisible = component.GetOrDefault<bool>("bVisible", true);
            else if (
                authorityComponent is not null &&
                HasSerializedProperty(authorityComponent, "bVisible"))
                explicitVisible =
                    authorityComponent.GetOrDefault<bool>("bVisible", true);

            bool? hiddenInGame = null;
            if (HasSerializedProperty(component, "bHiddenInGame"))
                hiddenInGame =
                    component.GetOrDefault<bool>("bHiddenInGame", false);
            else if (
                authorityComponent is not null &&
                HasSerializedProperty(authorityComponent, "bHiddenInGame"))
                hiddenInGame =
                    authorityComponent.GetOrDefault<bool>("bHiddenInGame", false);

            var effectiveVisible =
                explicitVisible ??
                (hiddenInGame is not null
                    ? !hiddenInGame.Value
                    : true);

            var autoActivate = InheritedValue(
                component,
                authorityComponent,
                "bAutoActivate",
                true);
            var secondsBeforeInactive = InheritedValue(
                component,
                authorityComponent,
                "SecondsBeforeInactive",
                1.0f);
            var customTimeDilation = InheritedValue(
                component,
                authorityComponent,
                "CustomTimeDilation",
                1.0f);
            var warmupTime = InheritedValue(
                component,
                authorityComponent,
                "WarmupTime",
                0.0f);
            var warmupTickRate = InheritedValue(
                component,
                authorityComponent,
                "WarmupTickRate",
                0.0f);
            var allowRecycling = InheritedValue(
                component,
                authorityComponent,
                "bAllowRecycling",
                false);
            var resetOnDetach = InheritedValue(
                component,
                authorityComponent,
                "bResetOnDetach",
                false);
            var skipUpdateDynamicDataDuringTick = InheritedValue(
                component,
                authorityComponent,
                "bSkipUpdateDynamicDataDuringTick",
                false);

            rows.Add(new
            {
                id = $"particle_{rows.Count:0000}",
                packagePath = logicalPackage,
                actorName = parentName,
                ownerExportType,
                ownerClassPath,
                componentName = component.Name,
                sourcePath = componentPath,
                hierarchy = BuildHierarchy(component, authorityComponent),
                componentAuthority = new
                {
                    objectPath = authorityComponent?.GetPathName(),
                    provenance = componentAuthority.provenance
                },
                template = new
                {
                    objectPath = templatePath,
                    exportType = templateType,
                    loaded = templateLoaded,
                    reference = templateIndex is { IsNull: false } ? templateIndex.ToString() : null,
                    provenance = templateProvenance
                },
                properties = new
                {
                    autoActivate,
                    effectiveVisible,
                    hiddenInGame = hiddenInGame ?? false,
                    secondsBeforeInactive,
                    customTimeDilation,
                    warmupTime,
                    warmupTickRate,
                    allowRecycling,
                    resetOnDetach,
                    skipUpdateDynamicDataDuringTick,
                    provenance = new
                    {
                        autoActivate = HasSerializedProperty(component, "bAutoActivate")
                            ? "instance"
                            : authorityComponent is not null &&
                              HasSerializedProperty(authorityComponent, "bAutoActivate")
                                ? "component_template"
                                : "native_default",
                        visibility = explicitVisible is not null || hiddenInGame is not null
                            ? (
                                HasSerializedProperty(component, "bVisible") ||
                                HasSerializedProperty(component, "bHiddenInGame")
                                    ? "instance"
                                    : "component_template"
                              )
                            : "native_default"
                    }
                }
            });
            }
            catch (Exception componentError)
            {
                componentFailures.Add(new {
                    packagePath = logicalPackage,
                    componentPath = component.GetPathName(),
                    error = componentError.GetType().Name + ": " + componentError.Message,
                    stack = componentError.StackTrace
                });
            }
        }
    }
    catch (Exception ex)
    {
        packageFailures.Add(new
        {
            packagePath = logicalPackage,
            error = ex.GetType().Name + ": " + ex.Message
        });
    }
}

var ready =
    packagesLoaded == mapPackages.Length &&
    packageFailures.Count == 0 &&
    componentFailures.Count == 0 &&
    rows.Count > 0 &&
    referencedTemplateCount > 0;

var output = new
{
    schemaVersion = 2,
    sourceGame = sourceGameName,
    coordinateSystem = new
    {
        source = "Unreal Engine centimeters",
        target = "XZIEL meters X,-Y,Z",
        hierarchyConvention = "component local transforms ordered child-to-parent"
    },
    mapPackageCount = mapPackages.Length,
    packagesLoaded,
    particleComponentCount = rows.Count,
    referencedTemplateCount,
    loadedTemplateCount,
    nullTemplateCount,
    templateTypeCounts,
    particleComponents = rows,
    packageFailures,
    componentFailures,
    ready
};

Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(output, new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_PARTICLE_SCENE_EXTRACT " +
    JsonSerializer.Serialize(new
    {
        output.mapPackageCount,
        output.packagesLoaded,
        output.particleComponentCount,
        output.referencedTemplateCount,
        output.loadedTemplateCount,
        output.nullTemplateCount,
        output.templateTypeCounts,
        packageFailureCount = packageFailures.Count,
        componentFailureCount = componentFailures.Count,
        output.ready
    }));

foreach (var failure in packageFailures.Take(20))
    Console.WriteLine("XZIEL_UE_PARTICLE_SCENE_PACKAGE_FAILURE " + JsonSerializer.Serialize(failure));

foreach (var failure in componentFailures.Take(40))
    Console.WriteLine("XZIEL_UE_PARTICLE_SCENE_COMPONENT_FAILURE " + JsonSerializer.Serialize(failure));

if (!ready)
{
    Console.WriteLine("XZIEL_UE_PARTICLE_SCENE_EXTRACT_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_PARTICLE_SCENE_EXTRACT_GREEN");
return 0;
