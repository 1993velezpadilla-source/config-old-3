using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Animation;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Assets.Exports.Sound;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Animations;
using CUE4Parse_Conversion.Dto;
using CUE4Parse_Conversion.Options;
using CUE4Parse_Conversion.Sounds;
using System.Text.Json;

if (args.Length != 7)
{
    Console.Error.WriteLine(
        "usage: UEDeepPayloadAudit <root> <mappings.usmap> <class-census.json> <output.json> <shard-index> <shard-count> <source-game>");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputPath = args[3];
var shardIndex = int.Parse(args[4]);
var shardCount = int.Parse(args[5]);
var sourceGameName = args[6];

if (shardCount <= 0 || shardIndex < 0 || shardIndex >= shardCount)
    throw new ArgumentOutOfRangeException(nameof(shardIndex));

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        _ => throw new ArgumentException("unsupported source-game: " + sourceGameName)
    };

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
var packageRows = censusDoc.RootElement.GetProperty("packages")
    .EnumerateArray()
    .Select((row, index) =>
    {
        var classes = row.GetProperty("classes");

        var textureCount = classes.EnumerateObject()
            .Where(p => p.Name.EndsWith("Texture2D", StringComparison.Ordinal))
            .Sum(p => p.Value.GetInt32());

        return new PackageRow(
            index,
            NormalizeMergedShardPath(
                row.GetProperty("packagePath").GetString()
                ?? throw new InvalidDataException("missing packagePath")),
            textureCount,
            GetClassCount(classes, "SoundWave"),
            GetClassCount(classes, "SkeletalMesh"),
            GetClassCount(classes, "AnimSequence"));
    })
    .Where(row =>
        row.TextureCount > 0 ||
        row.SoundWaveCount > 0 ||
        row.SkeletalMeshCount > 0 ||
        row.AnimSequenceCount > 0)
    .Where(row => row.Index % shardCount == shardIndex)
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

var failures = new List<object>();
var textureFormats = new SortedDictionary<string, int>(StringComparer.Ordinal);
var audioFormats = new SortedDictionary<string, int>(StringComparer.OrdinalIgnoreCase);

var expectedTextures = packageRows.Sum(x => x.TextureCount);
var expectedSoundWaves = packageRows.Sum(x => x.SoundWaveCount);
var expectedSkeletalMeshes = packageRows.Sum(x => x.SkeletalMeshCount);
var expectedAnimSequences = packageRows.Sum(x => x.AnimSequenceCount);

var packagesLoaded = 0;

var texturesDecoded = 0;
long textureMips = 0;
long textureBytes = 0;
var maxTextureWidth = 0;
var maxTextureHeight = 0;

var soundWavesDecoded = 0;
long audioBytes = 0;

var skeletalMeshesDecoded = 0;
long skeletalBones = 0;
long skeletalVertices = 0;
long skeletalIndices = 0;
long skeletalTriangles = 0;
var maxSkeletalUvChannels = 0;

var animSequencesDecoded = 0;
long animationFrames = 0;
long animationTracks = 0;
long animationPositionKeys = 0;
long animationRotationKeys = 0;
long animationScaleKeys = 0;

foreach (var row in packageRows)
{
    var resolved = ResolveProviderPackagePath(provider, row.Path);
    if (resolved is null)
    {
        failures.Add(new {
            family = "package",
            packagePath = row.Path,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;
        var exports = package.GetExports().ToArray();

        AuditTextures(row, exports.OfType<UTexture2D>().ToArray());
        AuditSoundWaves(row, exports.OfType<USoundWave>().ToArray());
        AuditSkeletalMeshes(row, exports.OfType<USkeletalMesh>().ToArray());
        AuditAnimSequences(row, exports.OfType<UAnimSequence>().ToArray());
    }
    catch (Exception e)
    {
        failures.Add(new {
            family = "package",
            packagePath = row.Path,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var ready =
    failures.Count == 0 &&
    packagesLoaded == packageRows.Length &&
    texturesDecoded == expectedTextures &&
    soundWavesDecoded == expectedSoundWaves &&
    skeletalMeshesDecoded == expectedSkeletalMeshes &&
    animSequencesDecoded == expectedAnimSequences &&
    (expectedTextures == 0 || textureBytes > 0) &&
    (expectedSoundWaves == 0 || audioBytes > 0) &&
    (expectedSkeletalMeshes == 0 || (skeletalVertices > 0 && skeletalIndices > 0)) &&
    (expectedAnimSequences == 0 || (animationFrames > 0 && animationTracks > 0));

var report = new {
    schemaVersion = 1,
    sourceGameName,
    shardIndex,
    shardCount,
    packageCount = packageRows.Length,
    packagesLoaded,
    expectedTextures,
    texturesDecoded,
    textureMips,
    textureBytes,
    textureFormats,
    maxTextureWidth,
    maxTextureHeight,
    expectedSoundWaves,
    soundWavesDecoded,
    audioBytes,
    audioFormats,
    expectedSkeletalMeshes,
    skeletalMeshesDecoded,
    skeletalBones,
    skeletalVertices,
    skeletalIndices,
    skeletalTriangles,
    maxSkeletalUvChannels,
    expectedAnimSequences,
    animSequencesDecoded,
    animationFrames,
    animationTracks,
    animationPositionKeys,
    animationRotationKeys,
    animationScaleKeys,
    failureCount = failures.Count,
    failures,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_DEEP_PAYLOAD_AUDIT " +
    JsonSerializer.Serialize(new {
        shardIndex,
        shardCount,
        packages = packageRows.Length,
        packagesLoaded,
        expectedTextures,
        texturesDecoded,
        textureMips,
        textureBytes,
        expectedSoundWaves,
        soundWavesDecoded,
        audioBytes,
        expectedSkeletalMeshes,
        skeletalMeshesDecoded,
        skeletalVertices,
        skeletalTriangles,
        expectedAnimSequences,
        animSequencesDecoded,
        animationFrames,
        animationTracks,
        failures = failures.Count,
        ready
    }));

if (!ready)
{
    foreach (var failure in failures.Take(150))
    {
        Console.WriteLine(
            "XZIEL_UE_DEEP_PAYLOAD_FAILURE " +
            JsonSerializer.Serialize(failure));
    }

    /*
     * The shard report is authoritative input to the global merge. Do not
     * abort the workflow here: every shard must run so the final gate exposes
     * the complete incompatibility set instead of stopping at the first one.
     */
    Console.WriteLine("XZIEL_UE_DEEP_PAYLOAD_SHARD_INCOMPLETE");
}
else
{
    Console.WriteLine("XZIEL_UE_DEEP_PAYLOAD_SHARD_GREEN");
}

return 0;

void AuditTextures(PackageRow row, UTexture2D[] textures)
{
    if (textures.Length != row.TextureCount)
    {
        failures.Add(new {
            family = "texture",
            packagePath = row.Path,
            error = $"texture count mismatch census={row.TextureCount} decoded={textures.Length}"
        });
        return;
    }

    foreach (var texture in textures)
    {
        try
        {
            var format = texture.Format.ToString();
            if (format == "PF_Unknown")
                throw new InvalidDataException("unknown texture pixel format");

            if (texture.PlatformData.SizeX <= 0 || texture.PlatformData.SizeY <= 0)
                throw new InvalidDataException(
                    $"invalid texture dimensions {texture.PlatformData.SizeX}x{texture.PlatformData.SizeY}");

            if (texture.PlatformData.Mips.Length <= 0)
                throw new InvalidDataException("texture has no cooked mips");

            long objectBytes = 0;
            for (var mipIndex = 0; mipIndex < texture.PlatformData.Mips.Length; ++mipIndex)
            {
                var mip = texture.GetMip(mipIndex)
                    ?? throw new InvalidDataException($"mip {mipIndex} could not be resolved");

                var data = mip.BulkData?.Data;
                if (data is null || data.Length == 0)
                    throw new InvalidDataException($"mip {mipIndex} has no bulk payload");

                if (mip.SizeX <= 0 || mip.SizeY <= 0)
                    throw new InvalidDataException(
                        $"mip {mipIndex} has invalid dimensions {mip.SizeX}x{mip.SizeY}");

                objectBytes += data.LongLength;
                textureMips++;
            }

            if (objectBytes <= 0)
                throw new InvalidDataException("texture resolved zero payload bytes");

            textureBytes += objectBytes;
            texturesDecoded++;
            textureFormats[format] = textureFormats.GetValueOrDefault(format) + 1;
            maxTextureWidth = Math.Max(maxTextureWidth, texture.PlatformData.SizeX);
            maxTextureHeight = Math.Max(maxTextureHeight, texture.PlatformData.SizeY);
        }
        catch (Exception e)
        {
            failures.Add(new {
                family = "texture",
                packagePath = row.Path,
                objectPath = texture.GetPathName(),
                error = e.GetType().FullName + ": " + e.Message
            });
        }
    }
}

void AuditSoundWaves(PackageRow row, USoundWave[] waves)
{
    if (waves.Length != row.SoundWaveCount)
    {
        failures.Add(new {
            family = "audio",
            packagePath = row.Path,
            error = $"sound wave count mismatch census={row.SoundWaveCount} decoded={waves.Length}"
        });
        return;
    }

    foreach (var wave in waves)
    {
        try
        {
            wave.Decode(
                shouldDecompress: false,
                out var audioFormat,
                out var data);

            if (string.IsNullOrWhiteSpace(audioFormat))
                throw new InvalidDataException("sound wave has no resolved audio format");
            if (data is null || data.Length == 0)
                throw new InvalidDataException("sound wave has no resolved compressed payload");

            soundWavesDecoded++;
            audioBytes += data.LongLength;
            audioFormats[audioFormat] =
                audioFormats.GetValueOrDefault(audioFormat) + 1;
        }
        catch (Exception e)
        {
            failures.Add(new {
                family = "audio",
                packagePath = row.Path,
                objectPath = wave.GetPathName(),
                error = e.GetType().FullName + ": " + e.Message
            });
        }
    }
}

void AuditSkeletalMeshes(PackageRow row, USkeletalMesh[] meshes)
{
    if (meshes.Length != row.SkeletalMeshCount)
    {
        failures.Add(new {
            family = "skeletal_mesh",
            packagePath = row.Path,
            error = $"skeletal mesh count mismatch census={row.SkeletalMeshCount} decoded={meshes.Length}"
        });
        return;
    }

    foreach (var mesh in meshes)
    {
        try
        {
            using var dto = new SkeletalMeshDto(
                mesh,
                EMeshQuality.Highest,
                ENaniteMeshFormat.NoNanite,
                exportMorphTarget: false);

            if (dto.Bones.Length <= 0)
                throw new InvalidDataException("skeletal mesh has no reference bones");
            if (dto.LODs.Count <= 0)
                throw new InvalidDataException("skeletal mesh has no usable LOD");

            var lod = dto.LODs[0];
            if (lod.Vertices.Length <= 0 ||
                lod.Indices.Length <= 0 ||
                lod.Indices.Length % 3 != 0)
            {
                throw new InvalidDataException(
                    $"invalid skeletal geometry vertices={lod.Vertices.Length} indices={lod.Indices.Length}");
            }

            var uvChannels = 1 + lod.ExtraUvs.Length;
            if (uvChannels > 8)
                throw new InvalidDataException(
                    $"skeletal mesh uses {uvChannels} UV channels; native XZMS maximum is 8");

            skeletalMeshesDecoded++;
            skeletalBones += dto.Bones.Length;
            skeletalVertices += lod.Vertices.Length;
            skeletalIndices += lod.Indices.Length;
            skeletalTriangles += lod.Indices.Length / 3;
            maxSkeletalUvChannels = Math.Max(maxSkeletalUvChannels, uvChannels);
        }
        catch (Exception e)
        {
            failures.Add(new {
                family = "skeletal_mesh",
                packagePath = row.Path,
                objectPath = mesh.GetPathName(),
                error = e.GetType().FullName + ": " + e.Message
            });
        }
    }
}

void AuditAnimSequences(PackageRow row, UAnimSequence[] animations)
{
    if (animations.Length != row.AnimSequenceCount)
    {
        failures.Add(new {
            family = "animation",
            packagePath = row.Path,
            error = $"animation count mismatch census={row.AnimSequenceCount} decoded={animations.Length}"
        });
        return;
    }

    foreach (var animation in animations)
    {
        try
        {
            var skeleton = ResolveAnimationSkeleton(
                provider,
                animation,
                out var skeletonSourcePath);

            var converted = skeleton.ConvertAnims(animation);

            if (converted.Sequences.Count != 1)
                throw new InvalidDataException(
                    $"animation conversion produced {converted.Sequences.Count} sequences");

            var sequence = converted.Sequences[0];
            if (sequence.NumFrames <= 0)
                throw new InvalidDataException("animation has no frames");
            if (sequence.Tracks.Count <= 0)
                throw new InvalidDataException("animation has no decoded tracks");

            long positionKeys = 0;
            long rotationKeys = 0;
            long scaleKeys = 0;
            foreach (var track in sequence.Tracks)
            {
                positionKeys += track.KeyPos?.Length ?? 0;
                rotationKeys += track.KeyQuat?.Length ?? 0;
                scaleKeys += track.KeyScale?.Length ?? 0;
            }

            if (positionKeys + rotationKeys + scaleKeys <= 0)
                throw new InvalidDataException("animation decoded zero transform keys");

            animSequencesDecoded++;
            animationFrames += sequence.NumFrames;
            animationTracks += sequence.Tracks.Count;
            animationPositionKeys += positionKeys;
            animationRotationKeys += rotationKeys;
            animationScaleKeys += scaleKeys;
        }
        catch (Exception e)
        {
            string? skeletonPath = null;
            string? skeletonPackage = null;
            string? skeletonClass = null;
            var skeletonIndex = animation.Skeleton?.Index;

            try
            {
                var resolvedSkeleton =
                    animation.Skeleton?.ResolvedObjectNoCache;
                skeletonPath =
                    resolvedSkeleton?.GetPathName();
                skeletonPackage =
                    resolvedSkeleton?.Package.Name;
                skeletonClass =
                    resolvedSkeleton?.Class?.Name.Text;
            }
            catch
            {
                // Preserve the primary animation failure unchanged.
            }

            failures.Add(new {
                family = "animation",
                packagePath = row.Path,
                objectPath = animation.GetPathName(),
                skeletonIndex,
                skeletonPath,
                skeletonPackage,
                skeletonClass,
                error = e.GetType().FullName + ": " + e.Message
            });
        }
    }
}


static USkeleton ResolveAnimationSkeleton(
    DefaultFileProvider provider,
    UAnimSequence animation,
    out string sourcePackagePath)
{
    var resolved =
        animation.Skeleton?.ResolvedObjectNoCache
        ?? throw new InvalidDataException(
            "animation has no resolvable Skeleton object reference");

    var objectPath = resolved.GetPathName();
    if (string.IsNullOrWhiteSpace(objectPath))
        throw new InvalidDataException(
            "animation Skeleton reference has no object path");

    var dot = objectPath.LastIndexOf('.');
    var virtualPackagePath =
        (dot > 0 ? objectPath[..dot] : objectPath)
        .Replace('\\', '/')
        .Trim();

    var objectName =
        dot > 0 && dot + 1 < objectPath.Length
            ? objectPath[(dot + 1)..]
            : virtualPackagePath.Split('/').Last();

    var normalizedVirtual =
        virtualPackagePath.TrimStart('/');

    var candidates = new List<string>
    {
        normalizedVirtual + ".uasset"
    };

    var firstSlash = normalizedVirtual.IndexOf('/');
    if (firstSlash > 0 && firstSlash + 1 < normalizedVirtual.Length)
    {
        var pluginName = normalizedVirtual[..firstSlash];
        var pluginRelative = normalizedVirtual[(firstSlash + 1)..];

        /*
         * Generic Unreal plugin mount:
         *   /PluginName/Folder/Asset.Asset
         * maps to a physical package under:
         *   .../Plugins/PluginName/Content/Folder/Asset.uasset
         */
        candidates.Add(
            $"Plugins/{pluginName}/Content/{pluginRelative}.uasset");
    }

    string? providerKey = null;
    foreach (var suffix in candidates.Distinct(StringComparer.OrdinalIgnoreCase))
    {
        var matches = provider.Files.Keys
            .Where(key =>
                key.EndsWith(
                    suffix,
                    StringComparison.OrdinalIgnoreCase))
            .OrderBy(key => key.Length)
            .ThenBy(key => key, StringComparer.OrdinalIgnoreCase)
            .Take(2)
            .ToArray();

        if (matches.Length == 1)
        {
            providerKey = matches[0];
            break;
        }

        if (matches.Length > 1)
        {
            throw new InvalidDataException(
                $"ambiguous Skeleton package resolution for {objectPath}: " +
                string.Join(", ", matches));
        }
    }

    if (providerKey is null)
    {
        throw new FileNotFoundException(
            $"Skeleton package unresolved for {objectPath}; tried " +
            string.Join(", ", candidates));
    }

    sourcePackagePath = providerKey;
    var package = provider.LoadPackage(providerKey);

    var skeletons = package.GetExports()
        .OfType<USkeleton>()
        .ToArray();

    var exact = skeletons
        .Where(s =>
            string.Equals(
                s.Name,
                objectName,
                StringComparison.OrdinalIgnoreCase))
        .ToArray();

    if (exact.Length == 1)
        return exact[0];

    if (exact.Length > 1)
        throw new InvalidDataException(
            $"multiple Skeleton exports named {objectName} in {providerKey}");

    if (skeletons.Length == 1)
        return skeletons[0];

    throw new InvalidDataException(
        $"Skeleton export {objectName} unresolved in {providerKey}; " +
        $"decoded skeleton exports={skeletons.Length}");
}

static int GetClassCount(JsonElement classes, string className)
{
    return classes.TryGetProperty(className, out var count)
        ? count.GetInt32()
        : 0;
}

static string NormalizeMergedShardPath(string path)
{
    var normalized = path.Replace('\\', '/');
    if (!normalized.StartsWith("shard-", StringComparison.OrdinalIgnoreCase))
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
    var normalized = logicalPath.Replace('\\', '/').TrimStart('/');

    if (provider.Files.ContainsKey(normalized))
        return normalized;

    var matches = provider.Files.Keys
        .Where(key => key.EndsWith(normalized, StringComparison.OrdinalIgnoreCase))
        .OrderBy(key => key.Length)
        .ThenBy(key => key, StringComparer.OrdinalIgnoreCase)
        .Take(2)
        .ToArray();

    return matches.Length == 1 ? matches[0] : null;
}

sealed record PackageRow(
    int Index,
    string Path,
    int TextureCount,
    int SoundWaveCount,
    int SkeletalMeshCount,
    int AnimSequenceCount);
