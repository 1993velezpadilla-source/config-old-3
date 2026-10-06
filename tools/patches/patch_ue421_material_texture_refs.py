#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/maps/UEMaterialAudit/Program.cs")
text = path.read_text(encoding="utf-8-sig")

old = r'''                var textures = new List<object>();
                foreach (var textureEntry in parameters.Textures
                             .OrderBy(
                                 row => row.Key,
                                 StringComparer.Ordinal))
                {
                    textureReferenceCount++;

                    if (textureEntry.Value is UTexture texture)
                    {
                        textureLoadCount++;
                        textures.Add(new
                        {
                            parameter = textureEntry.Key,
                            objectPath = texture.GetPathName(),
                            exportType = texture.ExportType,
                            loaded = true
                        });
                    }
                    else
                    {
                        var unresolved = new
                        {
                            materialPath = material.GetPathName(),
                            parameter = textureEntry.Key,
                            reference =
                                textureEntry.Value.ToString(),
                            referenceType =
                                textureEntry.Value.GetType().FullName
                        };
                        unresolvedTextureRefs.Add(unresolved);
                        textures.Add(new
                        {
                            parameter = textureEntry.Key,
                            objectPath = (string?)null,
                            exportType = (string?)null,
                            loaded = false,
                            reference =
                                textureEntry.Value.ToString(),
                            referenceType =
                                textureEntry.Value.GetType().FullName
                        });
                    }
                }
'''

new = r'''                var textureTruth =
                    ResolveAuthoritativeTextureReferences(
                        material,
                        provider);

                // CMaterialParams2 still contributes expression/cached texture
                // references when available. Cooked UE4.21 MaterialInstance
                // parents often fail provider-side loading, so the explicit
                // TextureParameterValues resolver above is the authority for
                // those instances and parent chains.
                foreach (var textureEntry in parameters.Textures)
                {
                    var key = textureEntry.Key;
                    if (textureEntry.Value is UTexture loadedTexture)
                    {
                        textureTruth[key] = new TextureTruth(
                            key,
                            loadedTexture.GetPathName(),
                            loadedTexture.ExportType,
                            true,
                            loadedTexture.GetPathName(),
                            loadedTexture.GetType().FullName);
                    }
                    else if (textureEntry.Value is not null &&
                             !textureTruth.ContainsKey(key))
                    {
                        var reference = textureEntry.Value.ToString();
                        textureTruth[key] = new TextureTruth(
                            key,
                            textureEntry.Value.GetPathName(),
                            textureEntry.Value.ExportType,
                            false,
                            reference,
                            textureEntry.Value.GetType().FullName);
                    }
                }

                var textures = new List<object>();
                foreach (var pair in textureTruth
                             .OrderBy(
                                 row => row.Key,
                                 StringComparer.Ordinal))
                {
                    var truth = pair.Value;
                    textureReferenceCount++;

                    if (truth.Loaded)
                        textureLoadCount++;

                    if (string.IsNullOrWhiteSpace(truth.ObjectPath))
                    {
                        unresolvedTextureRefs.Add(new
                        {
                            materialPath = material.GetPathName(),
                            parameter = truth.Parameter,
                            reference = truth.Reference,
                            referenceType = truth.ReferenceType
                        });
                    }

                    textures.Add(new
                    {
                        parameter = truth.Parameter,
                        objectPath = truth.ObjectPath,
                        exportType = truth.ExportType,
                        loaded = truth.Loaded,
                        reference = truth.Reference,
                        referenceType = truth.ReferenceType
                    });
                }
'''

if old not in text:
    raise SystemExit("texture collection block missing")
text = text.replace(old, new, 1)

anchor = r'''static (
    bool resolved,
'''
helper = r'''static Dictionary<string, TextureTruth>
ResolveAuthoritativeTextureReferences(
    UUnrealMaterial material,
    DefaultFileProvider provider,
    HashSet<string>? visiting = null)
{
    visiting ??= new HashSet<string>(
        StringComparer.OrdinalIgnoreCase);

    var result = new Dictionary<string, TextureTruth>(
        StringComparer.Ordinal);
    var materialPath = material.GetPathName();
    if (!visiting.Add(materialPath))
        return result;

    try
    {
        if (material is UMaterialInstance instance)
        {
            UUnrealMaterial? parent = instance.Parent;

            if (parent is null)
            {
                var rawParentProperty =
                    instance.Properties.FirstOrDefault(
                        p => p.Name.Text.Equals(
                            "Parent",
                            StringComparison.Ordinal));

                if (rawParentProperty?.Tag?.GenericValue
                        is FPackageIndex rawParent &&
                    !rawParent.IsNull)
                {
                    if (rawParent.TryLoad<UUnrealMaterial>(
                            out var rawLoadedParent) &&
                        rawLoadedParent is not null &&
                        rawLoadedParent != material)
                    {
                        parent = rawLoadedParent;
                    }
                    else
                    {
                        parent = ResolveMaterialByRawReference(
                            provider,
                            rawParent.ResolvedObject?.GetPathName()
                                ?? rawParent.ToString());
                    }
                }
            }

            if (parent is not null && parent != material)
            {
                foreach (var inherited in
                         ResolveAuthoritativeTextureReferences(
                             parent,
                             provider,
                             visiting))
                {
                    result[inherited.Key] = inherited.Value;
                }
            }
        }

        if (material is UMaterialInstanceConstant constant)
        {
            foreach (var parameter in
                     constant.TextureParameterValues)
            {
                var reference = parameter.ParameterValue;
                if (reference is null || reference.IsNull)
                    continue;

                UTexture? loaded = null;
                reference.TryLoad<UTexture>(out loaded);

                var objectPath =
                    loaded?.GetPathName()
                    ?? reference.ResolvedObject?.GetPathName();

                var name = parameter.Name;
                result[name] = new TextureTruth(
                    name,
                    objectPath,
                    loaded?.ExportType,
                    loaded is not null,
                    reference.ToString(),
                    reference.GetType().FullName);
            }
        }

        // Cooked base UMaterial graphs can keep exact texture authority only
        // on MaterialExpressionTextureSample exports. CMaterialParams2 may
        // expose zero textures for these materials, so recover only explicit
        // source properties named Texture. Do not assign diffuse/normal
        // semantics here; downstream code may use them only when unambiguous.
        if (material is UMaterial baseMaterial)
        {
            for (var expressionIndex = 0;
                 expressionIndex < baseMaterial.Expressions.Length;
                 ++expressionIndex)
            {
                var expressionRef =
                    baseMaterial.Expressions[expressionIndex];

                if (!expressionRef.TryLoad(
                        out CUE4Parse.UE4.Assets.Exports.UObject
                            expression) ||
                    expression is null)
                    continue;

                var expressionTextureRecorded = false;
                foreach (var property in expression.Properties)
                {
                    if (!property.Name.Text.Equals(
                            "Texture",
                            StringComparison.OrdinalIgnoreCase))
                        continue;

                    var value = property.Tag?.GenericValue;
                    UTexture? loadedTexture = null;
                    string? objectPath = null;
                    string? exportType = null;
                    string? reference = null;
                    string? referenceType = null;

                    if (value is FPackageIndex textureRef &&
                        !textureRef.IsNull)
                    {
                        textureRef.TryLoad<UTexture>(
                            out loadedTexture);
                        objectPath =
                            loadedTexture?.GetPathName()
                            ?? textureRef.ResolvedObject?.GetPathName();
                        exportType = loadedTexture?.ExportType;
                        reference = textureRef.ToString();
                        referenceType =
                            textureRef.GetType().FullName;
                    }
                    else if (value is UTexture directTexture)
                    {
                        loadedTexture = directTexture;
                        objectPath = directTexture.GetPathName();
                        exportType = directTexture.ExportType;
                        reference = objectPath;
                        referenceType =
                            directTexture.GetType().FullName;
                    }

                    if (string.IsNullOrWhiteSpace(objectPath))
                        continue;

                    var name =
                        $"ExpressionTexture_{expressionIndex}_" +
                        property.Name.Text;
                    result[name] = new TextureTruth(
                        name,
                        objectPath,
                        exportType,
                        loadedTexture is not null,
                        reference,
                        referenceType);
                    expressionTextureRecorded = true;
                }

                // Several cooked UE4.21 MaterialExpressionTextureSample
                // subclasses deserialize Texture into a typed field/property
                // instead of leaving it in UObject.Properties. Recover that
                // source reference reflection-safely so the audit works across
                // CUE4Parse revisions without hard-binding a specific class.
                if (!expressionTextureRecorded)
                {
                    var flags =
                        System.Reflection.BindingFlags.Instance |
                        System.Reflection.BindingFlags.Public |
                        System.Reflection.BindingFlags.NonPublic;
                    object? runtimeValue = null;

                    var runtimeProperty =
                        expression.GetType().GetProperty(
                            "Texture",
                            flags);
                    if (runtimeProperty is not null &&
                        runtimeProperty.GetIndexParameters().Length == 0)
                    {
                        try
                        {
                            runtimeValue =
                                runtimeProperty.GetValue(expression);
                        }
                        catch
                        {
                        }
                    }

                    if (runtimeValue is null)
                    {
                        var runtimeField =
                            expression.GetType().GetField(
                                "Texture",
                                flags);
                        if (runtimeField is not null)
                        {
                            try
                            {
                                runtimeValue =
                                    runtimeField.GetValue(expression);
                            }
                            catch
                            {
                            }
                        }
                    }

                    UTexture? loadedTexture = null;
                    string? objectPath = null;
                    string? exportType = null;
                    string? reference = null;
                    string? referenceType = null;

                    if (runtimeValue is FPackageIndex runtimeTextureRef &&
                        !runtimeTextureRef.IsNull)
                    {
                        runtimeTextureRef.TryLoad<UTexture>(
                            out loadedTexture);
                        objectPath =
                            loadedTexture?.GetPathName()
                            ?? runtimeTextureRef.ResolvedObject?.GetPathName();
                        exportType = loadedTexture?.ExportType;
                        reference = runtimeTextureRef.ToString();
                        referenceType =
                            runtimeTextureRef.GetType().FullName;
                    }
                    else if (runtimeValue is UTexture runtimeTexture)
                    {
                        loadedTexture = runtimeTexture;
                        objectPath = runtimeTexture.GetPathName();
                        exportType = runtimeTexture.ExportType;
                        reference = objectPath;
                        referenceType =
                            runtimeTexture.GetType().FullName;
                    }

                    if (!string.IsNullOrWhiteSpace(objectPath))
                    {
                        var name =
                            $"ExpressionTexture_{expressionIndex}_Texture";
                        result[name] = new TextureTruth(
                            name,
                            objectPath,
                            exportType,
                            loadedTexture is not null,
                            reference,
                            referenceType);
                    }
                }
            }
        }

        return result;
    }
    finally
    {
        visiting.Remove(materialPath);
    }
}

'''
if anchor not in text:
    raise SystemExit("helper insertion anchor missing")
text = text.replace(anchor, helper + anchor, 1)

if "sealed record TextureTruth(" not in text:
    text = text.rstrip() + r"""

sealed record TextureTruth(
    string Parameter,
    string? ObjectPath,
    string? ExportType,
    bool Loaded,
    string? Reference,
    string? ReferenceType);
""" + "\n"

path.write_text(text, encoding="utf-8")
print("XZOGOT_UE421_MATERIAL_TEXTURE_REFERENCE_PATCH_GREEN")
