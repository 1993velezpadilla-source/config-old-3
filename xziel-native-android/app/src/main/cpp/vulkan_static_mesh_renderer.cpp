#include "vulkan_static_mesh_renderer.hpp"

#include "xziel/texture_container.hpp"
#include "xziel/streaming.hpp"
#include "xziel/sanctum.hpp"

#include <android/bitmap.h>
#include <android/imagedecoder.h>
#include <android/log.h>
#include <sys/system_properties.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <limits>
#include <span>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace xziel::android {

namespace {

constexpr const char* kTag = "XzielSanctumMesh";

void logInfo(const char* message) noexcept {
    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "%s",
        message);
}

void logError(const char* message) noexcept {
    __android_log_print(
        ANDROID_LOG_ERROR,
        kTag,
        "%s",
        message);
}

[[nodiscard]] bool ok(VkResult result) noexcept {
    return result == VK_SUCCESS;
}

[[nodiscard]] bool runtimeStreamingProbeEnabled() noexcept {
    char value[PROP_VALUE_MAX]{};

    const int length =
        __system_property_get(
            "debug.xziel.streaming_probe",
            value);

    return
        length > 0 &&
        std::strcmp(value, "1") == 0;
}

[[nodiscard]] bool runtimeGeometryStreamingProbeEnabled() noexcept {
    char value[PROP_VALUE_MAX]{};

    const int length =
        __system_property_get(
            "debug.xziel.geometry_streaming_probe",
            value);

    return
        length > 0 &&
        std::strcmp(value, "1") == 0;
}

std::string textureAssetPath(
    const std::string& exportedName,
    const char* extension) {
    std::string path = exportedName;

    if (path.ends_with(".png")) {
        path.resize(
            path.size() - 4U);
    } else if (path.ends_with(".ktx2")) {
        path.resize(
            path.size() - 5U);
    }

    path += extension;
    return path;
}

[[nodiscard]] bool isExactStGilesExteriorReference(
    const std::string& exportedName,
    bool srgb) noexcept {
    return
        srgb &&
        exportedName.find(
            "StGilesCripplegateExterior04") !=
            std::string::npos;
}

[[nodiscard]] std::uint64_t
chooseTextureResidentBudget(
    VkPhysicalDevice physicalDevice,
    VkPhysicalDeviceType deviceType) noexcept {
    constexpr std::uint64_t kMiB =
        1024ULL * 1024ULL;
    constexpr std::uint64_t kMinimum =
        96ULL * kMiB;
    constexpr std::uint64_t kMaximum =
        384ULL * kMiB;

    if (deviceType ==
        VK_PHYSICAL_DEVICE_TYPE_CPU) {
        return 128ULL * kMiB;
    }

    VkPhysicalDeviceMemoryProperties memory{};
    vkGetPhysicalDeviceMemoryProperties(
        physicalDevice,
        &memory);

    std::uint64_t largestDeviceLocalHeap = 0U;

    for (std::uint32_t i = 0U;
         i < memory.memoryHeapCount;
         ++i) {
        if ((memory.memoryHeaps[i].flags &
             VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) == 0U) {
            continue;
        }

        largestDeviceLocalHeap =
            std::max<std::uint64_t>(
                largestDeviceLocalHeap,
                static_cast<std::uint64_t>(
                    memory.memoryHeaps[i].size));
    }

    if (largestDeviceLocalHeap == 0U) {
        return 128ULL * kMiB;
    }

    return std::clamp<std::uint64_t>(
        largestDeviceLocalHeap / 8U,
        kMinimum,
        kMaximum);
}

[[nodiscard]] std::uint64_t
chooseGeometryResidentBudget(
    VkPhysicalDevice physicalDevice,
    VkPhysicalDeviceType deviceType) noexcept {
    constexpr std::uint64_t kMiB =
        1024ULL * 1024ULL;
    constexpr std::uint64_t kMinimum =
        64ULL * kMiB;
    constexpr std::uint64_t kMaximum =
        160ULL * kMiB;

    if (deviceType ==
        VK_PHYSICAL_DEVICE_TYPE_CPU) {
        return 96ULL * kMiB;
    }

    VkPhysicalDeviceMemoryProperties memory{};
    vkGetPhysicalDeviceMemoryProperties(
        physicalDevice,
        &memory);

    std::uint64_t largestDeviceLocalHeap = 0U;

    for (std::uint32_t i = 0U;
         i < memory.memoryHeapCount;
         ++i) {
        if ((memory.memoryHeaps[i].flags &
             VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) == 0U) {
            continue;
        }

        largestDeviceLocalHeap =
            std::max<std::uint64_t>(
                largestDeviceLocalHeap,
                static_cast<std::uint64_t>(
                    memory.memoryHeaps[i].size));
    }

    if (largestDeviceLocalHeap == 0U) {
        return 96ULL * kMiB;
    }

    return std::clamp<std::uint64_t>(
        largestDeviceLocalHeap / 16U,
        kMinimum,
        kMaximum);
}

[[nodiscard]] std::uint64_t
effectiveGeometryResidentBudget(
    std::uint64_t baseBudget,
    MemoryPressure pressure) noexcept {
    constexpr std::uint64_t kMiB =
        1024ULL * 1024ULL;

    switch (pressure) {
    case MemoryPressure::Critical:
        return std::max<std::uint64_t>(
            32ULL * kMiB,
            baseBudget / 2U);

    case MemoryPressure::Elevated:
        return std::max<std::uint64_t>(
            48ULL * kMiB,
            (baseBudget * 3U) / 4U);

    case MemoryPressure::Normal:
    default:
        return baseBudget;
    }
}

struct PackedStaticMeshVertex {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    std::array<std::int16_t, 4> normal{};
    std::array<std::uint16_t, 2> uv{};
};

static_assert(
    sizeof(PackedStaticMeshVertex) == 24U,
    "packed static GPU vertex must remain 24 bytes");

[[nodiscard]] bool supportsVertexFormat(
    VkPhysicalDevice physicalDevice,
    VkFormat format) noexcept {
    VkFormatProperties properties{};
    vkGetPhysicalDeviceFormatProperties(
        physicalDevice,
        format,
        &properties);

    return
        (properties.bufferFeatures &
         VK_FORMAT_FEATURE_VERTEX_BUFFER_BIT) != 0U;
}

[[nodiscard]] bool supportsPackedStaticVertex(
    VkPhysicalDevice physicalDevice) noexcept {
    return
        supportsVertexFormat(
            physicalDevice,
            VK_FORMAT_R16G16B16A16_SNORM) &&
        supportsVertexFormat(
            physicalDevice,
            VK_FORMAT_R16G16_UNORM);
}

[[nodiscard]] std::size_t gpuStaticVertexStride(
    bool packed) noexcept {
    return
        packed
        ? sizeof(PackedStaticMeshVertex)
        : sizeof(StaticMeshVertex);
}

[[nodiscard]] std::int16_t packSnorm16(
    float value) noexcept {
    if (!std::isfinite(value)) {
        return 0;
    }

    const float clamped =
        std::clamp(
            value,
            -1.0f,
            1.0f);

    return static_cast<std::int16_t>(
        std::lround(
            clamped * 32767.0f));
}

[[nodiscard]] std::uint16_t packUnorm16(
    float value) noexcept {
    if (!std::isfinite(value)) {
        return 0U;
    }

    const float clamped =
        std::clamp(
            value,
            0.0f,
            1.0f);

    return static_cast<std::uint16_t>(
        std::lround(
            clamped * 65535.0f));
}

[[nodiscard]] bool assetUvFitsUnorm16(
    const StaticMeshAsset& asset) noexcept {
    // Blender can legally author tiled UVs outside [0,1]. Do not silently
    // clamp those assets: use the original 36-byte layout instead.
    constexpr float kTolerance = 1.0e-5f;

    for (const auto& batch : asset.batches) {
        for (const auto& vertex : batch.vertices) {
            if (!std::isfinite(vertex.u) ||
                !std::isfinite(vertex.v) ||
                vertex.u < -kTolerance ||
                vertex.u > 1.0f + kTolerance ||
                vertex.v < -kTolerance ||
                vertex.v > 1.0f + kTolerance) {
                return false;
            }
        }
    }

    return true;
}

void packStaticVertex(
    const StaticMeshVertex& source,
    PackedStaticMeshVertex& destination) noexcept {
    destination.x = source.x;
    destination.y = source.y;
    destination.z = source.z;

    destination.normal = {
        packSnorm16(source.nx),
        packSnorm16(source.ny),
        packSnorm16(source.nz),
        0,
    };

    destination.uv = {
        packUnorm16(source.u),
        packUnorm16(source.v),
    };
}

void writeGpuVertices(
    std::span<const StaticMeshVertex> source,
    std::byte* destination,
    bool packed) noexcept {
    if (destination == nullptr ||
        source.empty()) {
        return;
    }

    if (!packed) {
        std::memcpy(
            destination,
            source.data(),
            source.size_bytes());
        return;
    }

    for (std::size_t i = 0U;
         i < source.size();
         ++i) {
        PackedStaticMeshVertex vertex{};
        packStaticVertex(
            source[i],
            vertex);

        std::memcpy(
            destination +
                i *
                sizeof(PackedStaticMeshVertex),
            &vertex,
            sizeof(vertex));
    }
}

[[nodiscard]] bool packGpuVerticesFromBytes(
    std::span<const std::byte> source,
    std::uint32_t vertexCount,
    std::byte* destination) noexcept {
    if (destination == nullptr ||
        vertexCount == 0U ||
        source.size() !=
            static_cast<std::size_t>(
                vertexCount) *
                sizeof(StaticMeshVertex)) {
        return false;
    }

    for (std::uint32_t i = 0U;
         i < vertexCount;
         ++i) {
        StaticMeshVertex sourceVertex{};

        std::memcpy(
            &sourceVertex,
            source.data() +
                static_cast<std::size_t>(i) *
                    sizeof(StaticMeshVertex),
            sizeof(sourceVertex));

        PackedStaticMeshVertex vertex{};
        packStaticVertex(
            sourceVertex,
            vertex);

        std::memcpy(
            destination +
                static_cast<std::size_t>(i) *
                    sizeof(PackedStaticMeshVertex),
            &vertex,
            sizeof(vertex));
    }

    return true;
}

[[nodiscard]] bool assetExists(
    AAssetManager* assetManager,
    const std::string& path) noexcept {
    if (assetManager == nullptr) {
        return false;
    }

    AAsset* asset =
        AAssetManager_open(
            assetManager,
            path.c_str(),
            AASSET_MODE_UNKNOWN);

    if (asset == nullptr) {
        return false;
    }

    AAsset_close(asset);
    return true;
}

} // namespace

VulkanStaticMeshRenderer::~VulkanStaticMeshRenderer() {
    shutdown();
}

bool VulkanStaticMeshRenderer::initialize(
    VkPhysicalDevice physicalDevice,
    VkDevice device,
    VkQueue graphicsQueue,
    std::uint32_t graphicsQueueFamily,
    VkCommandPool commandPool,
    VkRenderPass renderPass,
    VkSampleCountFlagBits sampleCount,
    AAssetManager* assetManager,
    const char* modelAssetPath) noexcept {
    shutdown();

    if (physicalDevice == VK_NULL_HANDLE ||
        device == VK_NULL_HANDLE ||
        graphicsQueue == VK_NULL_HANDLE ||
        graphicsQueueFamily == UINT32_MAX ||
        commandPool == VK_NULL_HANDLE ||
        renderPass == VK_NULL_HANDLE ||
        sampleCount == 0U ||
        assetManager == nullptr ||
        modelAssetPath == nullptr) {
        return false;
    }

    physicalDevice_ = physicalDevice;
    device_ = device;

    VkPhysicalDeviceFeatures deviceFeatures{};
    vkGetPhysicalDeviceFeatures(
        physicalDevice_,
        &deviceFeatures);

    VkPhysicalDeviceProperties deviceProperties{};
    vkGetPhysicalDeviceProperties(
        physicalDevice_,
        &deviceProperties);

    samplerAnisotropyEnabled_ =
        deviceFeatures.samplerAnisotropy == VK_TRUE;

    const bool packedStaticVertexFormatsSupported =
        supportsPackedStaticVertex(
            physicalDevice_);

    astcLdrSupported_ =
        deviceFeatures.textureCompressionASTC_LDR ==
        VK_TRUE;
    // VulkanStaticMeshRenderer only uses multi-draw when the logical device
    // enables the corresponding core feature. VulkanClearRenderer mirrors
    // this physical-device capability into VkDeviceCreateInfo.
    multiDrawIndirectEnabled_ =
        deviceFeatures.multiDrawIndirect ==
        VK_TRUE;
    maxDrawIndirectCount_ =
        multiDrawIndirectEnabled_
        ? std::max<std::uint32_t>(
              1U,
              deviceProperties.limits.
                  maxDrawIndirectCount)
        : 1U;

    maxSamplerAnisotropy_ =
        samplerAnisotropyEnabled_
        ? std::clamp(
              deviceProperties.limits.maxSamplerAnisotropy,
              1.0f,
              8.0f)
        : 1.0f;

    // CPU Vulkan implementations such as CI llvmpipe emulate ASTC decode.
    // Huge all-at-once submits can serialize badly there. Real mobile GPUs
    // keep a much larger batch to minimize queue waits during startup.
    uploadBatchCommandLimit_ =
        deviceProperties.deviceType ==
            VK_PHYSICAL_DEVICE_TYPE_CPU
        ? 2U
        : 16U;

    textureResidentBudgetBytes_ =
        chooseTextureResidentBudget(
            physicalDevice_,
            deviceProperties.deviceType);
    textureResidentBytes_ = 0U;
    textureDegradedCount_ = 0U;

    geometryResidentBudgetBytes_ =
        chooseGeometryResidentBudget(
            physicalDevice_,
            deviceProperties.deviceType);
    geometryResidentBytes_ = 0U;

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STATIC_TEXTURE_CAPS astc=%d multi_draw_indirect=%d max_indirect_draws=%u aniso=%.1f upload_batch_commands=%u texture_budget_mb=%.1f",
        astcLdrSupported_ ? 1 : 0,
        multiDrawIndirectEnabled_ ? 1 : 0,
        static_cast<unsigned int>(
            maxDrawIndirectCount_),
        static_cast<double>(
            maxSamplerAnisotropy_),
        static_cast<unsigned int>(
            uploadBatchCommandLimit_),
        static_cast<double>(
            textureResidentBudgetBytes_) /
            (1024.0 * 1024.0));

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_INTEGER_DRAW_FLAGS_READY push_bytes=%u viewmodel_offset=%u material_flags_offset=%u",
        static_cast<unsigned int>(
            sizeof(PushConstants)),
        static_cast<unsigned int>(
            offsetof(
                PushConstants,
                viewmodelMode)),
        static_cast<unsigned int>(
            offsetof(
                PushConstants,
                materialFlags)));

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_CPU_CLAMPED_MATERIAL_CONSTANTS_READY");

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_PRECOMPUTED_MATERIAL_PUSH_CONSTANTS_READY");

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_PRECOMPUTED_LIGHTNING_BOOST_READY");


    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_GEOMETRY_BUDGET_READY budget_mb=%.2f",
        static_cast<double>(
            geometryResidentBudgetBytes_) /
            (1024.0 * 1024.0));

    graphicsQueue_ = graphicsQueue;
    graphicsQueueFamily_ = graphicsQueueFamily;
    commandPool_ = commandPool;
    renderPass_ = renderPass;
    sampleCount_ = sampleCount;

    StaticMeshAsset asset{};
    if (!loadModel(
            assetManager,
            modelAssetPath,
            asset)) {
        shutdown();
        return false;
    }

    const bool uvFitsUnorm16 =
        assetUvFitsUnorm16(asset);
    packedStaticVertexEnabled_ =
        packedStaticVertexFormatsSupported &&
        uvFitsUnorm16;

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STATIC_VERTEX_FORMAT packed=%u gpu_stride=%u source_stride=%u color_attribute=0 uv_unorm16=%u format_supported=%u",
        packedStaticVertexEnabled_ ? 1U : 0U,
        static_cast<unsigned int>(
            gpuStaticVertexStride(
                packedStaticVertexEnabled_)),
        static_cast<unsigned int>(
            sizeof(StaticMeshVertex)),
        uvFitsUnorm16 ? 1U : 0U,
        packedStaticVertexFormatsSupported ? 1U : 0U);

    const std::string modelPath =
        modelAssetPath != nullptr
        ? modelAssetPath
        : "";

    streamGraphReady_ =
        modelPath.find("/sanctum/") !=
            std::string::npos &&
        configureSanctumStreamingGraph(
            streamGraph_);

    if (streamGraphReady_) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_STREAM_GRAPH_ADJACENCY_READY cells=%u portals=%u entries=%u",
            static_cast<unsigned int>(
                streamGraph_.cellCount()),
            static_cast<unsigned int>(
                streamGraph_.portalCount()),
            static_cast<unsigned int>(
                streamGraph_.adjacencyEntryCount()));

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_STREAM_RESOURCE_DECISION_INDEX_READY bindings=%u unique=%u",
            static_cast<unsigned int>(
                streamGraph_.bindingCount()),
            static_cast<unsigned int>(
                streamGraph_.uniqueResourceCount()));
    }

    textureMipResidency_.reset();
    streamCellBounds_ = {};
    streamDecisionCount_ = 0U;
    cachedStreamPlanStats_ = {};
    cachedStreamPlanCell_ = 0U;
    cachedStreamPlanPressure_ =
        MemoryPressure::Normal;
    cachedStreamColdBatches_ = 0U;
    streamPlanBuildCount_ = 0U;
    streamPlanCacheHitCount_ = 0U;
    streamCellHeatRefreshCount_ = 0U;
    streamPlanDirty_ = true;
    streamPlanFrame_ = 0U;
    lastLoggedStreamCell_ = 0U;
    streamCellCandidate_ = 0U;
    streamCellStableFrames_ = 0U;
    streamCullingActive_ = false;
    streamCullLogged_ = false;
    streamResidencyProbeEnabled_ =
        streamGraphReady_ &&
        runtimeStreamingProbeEnabled();
    streamResidencyProbeComplete_ = false;
    streamResidencyProbeReloadComplete_ = false;
    streamResidencyProbeTextureIndex_ =
        UINT32_MAX;
    streamResidencyProbeReloadFrame_ = 0U;
    geometryResidencyProbeEnabled_ =
        streamGraphReady_ &&
        runtimeGeometryStreamingProbeEnabled();
    geometryResidencyProbeComplete_ = false;
    geometryResidencyProbeCellSlot_ = UINT32_MAX;
    geometryResidencyProbeReloadFrame_ = 0U;

    if (streamResidencyProbeEnabled_) {
        logInfo(
            "XZIEL_RUNTIME_TEXTURE_RELOAD_PROBE_ENABLED");
    }

    if (geometryResidencyProbeEnabled_) {
        logInfo(
            "XZIEL_RUNTIME_GEOMETRY_RELOAD_PROBE_ENABLED");
    }

    // Read KTX2 payloads on bounded worker threads while the render thread
    // creates pipelines/descriptors. Vulkan object creation and queue submits
    // stay on this thread; only APK asset I/O moves off-thread.
    asyncPrefetchQueued_ = 0U;

    if (astcLdrSupported_) {
        constexpr std::uint64_t kMiB =
            1024ULL * 1024ULL;

        const std::uint64_t prefetchBudget =
            std::clamp<std::uint64_t>(
                textureResidentBudgetBytes_ / 4U,
                16ULL * kMiB,
                96ULL * kMiB);

        const std::uint32_t workerCount =
            deviceProperties.deviceType ==
                VK_PHYSICAL_DEVICE_TYPE_CPU
            ? 1U
            : 2U;

        if (assetStreamer_.start(
                assetManager,
                workerCount,
                prefetchBudget)) {
            std::unordered_set<std::string>
                queuedPaths;

            const auto queueTexture =
                [&](const std::string& exportedName) {
                    if (exportedName.empty()) {
                        return;
                    }

                    const std::string path =
                        textureAssetPath(
                            exportedName,
                            ".ktx2");

                    if (!assetExists(
                            assetManager,
                            path) ||
                        !queuedPaths.insert(path).second) {
                        return;
                    }

                    if (assetStreamer_.enqueue(path)) {
                        ++asyncPrefetchQueued_;
                    }
                };

            bool skippedExactExteriorKtx = false;

            for (const auto& batch : asset.batches) {
                // EXACT_ST_GILES_KTX_PREFETCH_BYPASS_V1
                // Exact-source audit loads this one sRGB base color from PNG.
                // Do not waste async I/O on its ASTC derivative, otherwise
                // prefetch accounting reports queued=14/consumed=13 even
                // though every texture actually requested by the renderer
                // was consumed successfully.
                if (isExactStGilesExteriorReference(
                        batch.textureName,
                        true)) {
                    skippedExactExteriorKtx = true;
                } else {
                    queueTexture(batch.textureName);
                }

                if (!batch.pbrEnabled()) {
                    continue;
                }

                queueTexture(
                    batch.pbr.normalTextureName);
                queueTexture(
                    batch.pbr.ormTextureName);
                queueTexture(
                    batch.pbr.emissiveTextureName);
            }

            if (skippedExactExteriorKtx) {
                logInfo(
                    "XZIEL_EXACT_EXTERIOR_KTX_PREFETCH_BYPASS_READY");
            }

            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_ASYNC_ASTC_PREFETCH_READY workers=%u queued=%u buffer_mb=%.1f",
                static_cast<unsigned int>(
                    workerCount),
                static_cast<unsigned int>(
                    asyncPrefetchQueued_),
                static_cast<double>(
                    prefetchBudget) /
                    (1024.0 * 1024.0));
        }
    }

    if (!createPipeline(assetManager)) {
        shutdown();
        return false;
    }

    VkDescriptorPoolSize poolSize{};
    poolSize.type =
        VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    const std::uint32_t materialCount =
        static_cast<std::uint32_t>(
            std::max<std::size_t>(
                asset.batches.size(),
                1U));

    poolSize.descriptorCount =
        materialCount *
        4U *
        kDescriptorFrames;

    VkDescriptorPoolCreateInfo poolInfo{
        VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO
    };
    poolInfo.maxSets =
        materialCount *
        kDescriptorFrames;
    poolInfo.poolSizeCount = 1U;
    poolInfo.pPoolSizes = &poolSize;

    if (!ok(
            vkCreateDescriptorPool(
                device_,
                &poolInfo,
                nullptr,
                &descriptorPool_))) {
        logError("descriptor pool creation failed");
        shutdown();
        return false;
    }

    std::unordered_map<std::string, std::uint32_t>
        textureIndices;

    std::vector<std::uint32_t>
        batchMaterialIndices;

    std::uint32_t pbrMaterialCount = 0U;
    std::uint32_t photogrammetryPbrCount = 0U;
    std::uint32_t normalMapCount = 0U;
    std::uint32_t ormMapCount = 0U;
    std::uint32_t emissiveMapCount = 0U;
    std::uint32_t photoDetailMapCount = 0U;
    std::uint32_t reusedMaterialCount = 0U;

    const auto loadTexture =
        [&](const std::string& exportedName,
            bool srgb,
            std::uint32_t& outIndex) noexcept {
            if (exportedName.empty()) {
                return false;
            }

            const std::string cacheKey =
                exportedName +
                (srgb ? "#srgb" : "#linear");

            const auto found =
                textureIndices.find(cacheKey);

            if (found != textureIndices.end()) {
                outIndex = found->second;
                return true;
            }

            GpuTexture texture{};
            if (!createTexture(
                    assetManager,
                    exportedName,
                    srgb,
                    texture)) {
                return false;
            }

            texture.streamResourceId =
                streamResourceId(
                    cacheKey);
            texture.srgb = srgb;
            texture.physicallyResident = true;
            texture.runtimeLoadQueued = false;
            texture.descriptorResidentMask =
                static_cast<std::uint8_t>(
                    (1U << kDescriptorFrames) - 1U);

            if (texture.sourceMipLevels > 0U &&
                texture.sourceMipLevels <=
                    kMaxStreamedTextureMips) {
                TextureMipChainDesc desc{};
                desc.id =
                    texture.streamResourceId;
                desc.mipCount =
                    texture.sourceMipLevels;
                desc.mipBytes =
                    texture.sourceMipBytes;
                desc.residentBaseMip =
                    std::min(
                        texture.residentBaseMip,
                        desc.mipCount - 1U);
                desc.requestedBaseMip =
                    desc.residentBaseMip;
                desc.pinned = false;

                if (!textureMipResidency_.
                        registerTexture(
                            desc,
                            0U)) {
                    destroyTexture(texture);
                    return false;
                }
            }

            outIndex =
                static_cast<std::uint32_t>(
                    textures_.size());

            textures_.emplace_back(
                std::move(texture));
            textureIndices.emplace(
                cacheKey,
                outIndex);
            return true;
        };

    const auto bindStreamTexture =
        [&](SanctumZone zone,
            std::uint32_t textureIndex) noexcept {
            if (!streamGraphReady_ ||
                zone == SanctumZone::Unknown ||
                textureIndex >= textures_.size()) {
                return;
            }

            const auto& texture =
                textures_[textureIndex];

            std::uint64_t bytes =
                texture.residentPayloadBytes;

            if (bytes == 0U) {
                bytes =
                    texture.allocationBytes;
            }

            if (bytes == 0U) {
                const std::uint64_t pixels =
                    static_cast<std::uint64_t>(
                        texture.width) *
                    static_cast<std::uint64_t>(
                        texture.height);

                bytes =
                    std::max<std::uint64_t>(
                        1U,
                        pixels * 4U);
            }

            (void) streamGraph_.bindResource({
                .cellId =
                    static_cast<std::uint32_t>(
                        zone),
                .resourceId =
                    texture.streamResourceId,
                .kind =
                    StreamResourceKind::Texture,
                .bytes = bytes,
                .pinned = false,
            });
        };

    try {
        batchMaterialIndices.reserve(
            asset.batches.size());
        materials_.reserve(
            asset.batches.size());

        for (const auto& batch : asset.batches) {
            GpuMaterial material{};

            const auto streamZone =
                streamGraphReady_
                ? sanctumZoneForAssetName(
                      batch.textureName)
                : SanctumZone::Unknown;

            if (!loadTexture(
                    batch.textureName,
                    true,
                    material.albedoTextureIndex)) {
                logError(
                    "static mesh albedo texture load failed");
                shutdown();
                return false;
            }

            material.streamResourceId =
                textures_[
                    material.albedoTextureIndex].
                        streamResourceId;

            bindStreamTexture(
                streamZone,
                material.albedoTextureIndex);

            material.normalTextureIndex =
                material.albedoTextureIndex;
            material.ormTextureIndex =
                material.albedoTextureIndex;
            material.emissiveTextureIndex =
                material.albedoTextureIndex;

            material.baseColorFactor =
                batch.pbr.baseColorFactor;
            material.metallicFactor =
                batch.pbr.metallicFactor;
            material.roughnessFactor =
                batch.pbr.roughnessFactor;
            material.emissiveFactor =
                batch.pbr.emissiveFactor;
            material.normalScale =
                batch.pbr.normalScale;
            material.occlusionStrength =
                batch.pbr.occlusionStrength;
            material.pbrEnabled =
                batch.pbrEnabled();
            material.photogrammetryPbr =
                batch.photogrammetryPbr();

            if (material.photogrammetryPbr &&
                !material.pbrEnabled) {
                logError(
                    "photogrammetry PBR batch missing PBR material");
                shutdown();
                return false;
            }

            if (material.pbrEnabled &&
                !batch.pbr.normalTextureName.empty()) {
                if (!loadTexture(
                        batch.pbr.normalTextureName,
                        false,
                        material.normalTextureIndex)) {
                    logError(
                        "static mesh normal texture load failed");
                    shutdown();
                    return false;
                }
                bindStreamTexture(
                    streamZone,
                    material.normalTextureIndex);
                material.hasNormalTexture = true;
            }

            if (material.pbrEnabled &&
                !batch.pbr.ormTextureName.empty()) {
                if (!loadTexture(
                        batch.pbr.ormTextureName,
                        false,
                        material.ormTextureIndex)) {
                    logError(
                        "static mesh ORM texture load failed");
                    shutdown();
                    return false;
                }
                bindStreamTexture(
                    streamZone,
                    material.ormTextureIndex);
                material.hasOrmTexture = true;
            }

            if (material.pbrEnabled &&
                !batch.pbr.emissiveTextureName.empty()) {
                const bool emissiveSrgb =
                    !material.photogrammetryPbr;

                if (!loadTexture(
                        batch.pbr.emissiveTextureName,
                        emissiveSrgb,
                        material.emissiveTextureIndex)) {
                    logError(
                        "static mesh emissive texture load failed");
                    shutdown();
                    return false;
                }
                bindStreamTexture(
                    streamZone,
                    material.emissiveTextureIndex);
                material.hasEmissiveTexture = true;
            }

            material.pushMetallicFactor =
                std::clamp(
                    material.metallicFactor,
                    0.0f,
                    1.0f);
            material.pushRoughnessFactor =
                std::clamp(
                    material.roughnessFactor,
                    0.045f,
                    1.0f);
            material.pushNormalScale =
                std::max(
                    material.normalScale,
                    0.0f);
            material.pushOcclusionStrength =
                std::clamp(
                    material.occlusionStrength,
                    0.0f,
                    1.0f);
            material.pushMaterialFlags =
                (material.pbrEnabled ? 1U : 0U) |
                (material.hasNormalTexture ? 2U : 0U) |
                (material.hasOrmTexture ? 4U : 0U) |
                (material.hasEmissiveTexture ? 8U : 0U) |
                (material.photogrammetryPbr ? 16U : 0U);

            const auto sameMaterial =
                [](const GpuMaterial& a,
                   const GpuMaterial& b) noexcept {
                    return
                        a.streamResourceId ==
                            b.streamResourceId &&
                        a.albedoTextureIndex ==
                            b.albedoTextureIndex &&
                        a.normalTextureIndex ==
                            b.normalTextureIndex &&
                        a.ormTextureIndex ==
                            b.ormTextureIndex &&
                        a.emissiveTextureIndex ==
                            b.emissiveTextureIndex &&
                        a.baseColorFactor ==
                            b.baseColorFactor &&
                        a.metallicFactor ==
                            b.metallicFactor &&
                        a.roughnessFactor ==
                            b.roughnessFactor &&
                        a.emissiveFactor ==
                            b.emissiveFactor &&
                        a.normalScale ==
                            b.normalScale &&
                        a.occlusionStrength ==
                            b.occlusionStrength &&
                        a.pbrEnabled ==
                            b.pbrEnabled &&
                        a.photogrammetryPbr ==
                            b.photogrammetryPbr &&
                        a.hasNormalTexture ==
                            b.hasNormalTexture &&
                        a.hasOrmTexture ==
                            b.hasOrmTexture &&
                        a.hasEmissiveTexture ==
                            b.hasEmissiveTexture;
                };

            std::uint32_t materialIndex =
                UINT32_MAX;

            for (std::size_t i = 0U;
                 i < materials_.size();
                 ++i) {
                if (sameMaterial(
                        material,
                        materials_[i])) {
                    materialIndex =
                        static_cast<std::uint32_t>(
                            i);
                    break;
                }
            }

            if (materialIndex != UINT32_MAX) {
                ++reusedMaterialCount;
                batchMaterialIndices.push_back(
                    materialIndex);
                continue;
            }

            if (!createMaterialDescriptor(
                    material)) {
                logError(
                    "static mesh PBR material descriptor failed");
                shutdown();
                return false;
            }

            if (material.pbrEnabled) {
                ++pbrMaterialCount;
            }

            if (material.photogrammetryPbr) {
                ++photogrammetryPbrCount;
            }

            if (material.hasNormalTexture) {
                ++normalMapCount;
            }

            if (material.hasOrmTexture) {
                ++ormMapCount;
            }

            if (material.hasEmissiveTexture) {
                ++emissiveMapCount;

                if (material.photogrammetryPbr) {
                    ++photoDetailMapCount;
                }
            }

            materialIndex =
                static_cast<std::uint32_t>(
                    materials_.size());

            materials_.emplace_back(
                std::move(material));
            batchMaterialIndices.push_back(
                materialIndex);
        }
    } catch (...) {
        logError(
            "static mesh GPU material allocation failed");
        shutdown();
        return false;
    }

    if (streamGraphReady_ &&
        !textures_.empty()) {
        streamFallbackTextureIndex_ = 0U;
        auto& fallback =
            textures_[streamFallbackTextureIndex_];

        if (fallback.streamResourceId != 0U) {
            textureMipResidency_.setPinned(
                fallback.streamResourceId,
                true);
        }

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_STREAMING_FALLBACK_READY texture_index=%u resource_id=%llu",
            static_cast<unsigned int>(
                streamFallbackTextureIndex_),
            static_cast<unsigned long long>(
                fallback.streamResourceId));
    } else {
        streamFallbackTextureIndex_ =
            UINT32_MAX;
    }

    if (asyncPrefetchQueued_ > 0U) {
        const auto streamStats =
            assetStreamer_.stats();

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_ASYNC_ASTC_PREFETCH_DONE queued=%llu completed=%llu failed=%llu consumed=%llu bytes_mb=%.2f pending=%u",
            static_cast<unsigned long long>(
                streamStats.queued),
            static_cast<unsigned long long>(
                streamStats.completed),
            static_cast<unsigned long long>(
                streamStats.failed),
            static_cast<unsigned long long>(
                streamStats.consumed),
            static_cast<double>(
                streamStats.bytesRead) /
                (1024.0 * 1024.0),
            static_cast<unsigned int>(
                streamStats.pending));
    }

    if (streamGraphReady_ &&
        !assetStreamer_.running()) {
        constexpr std::uint64_t kGeometryStreamBudget =
            48ULL * 1024ULL * 1024ULL;

        const std::uint32_t geometryWorkerCount =
            deviceProperties.deviceType ==
                VK_PHYSICAL_DEVICE_TYPE_CPU
            ? 1U
            : 2U;

        (void) assetStreamer_.start(
            assetManager,
            geometryWorkerCount,
            kGeometryStreamBudget);
    }

    if (streamGraphReady_ &&
        assetStreamer_.running()) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_RUNTIME_ASSET_STREAMER_READY workers=1+ persistent=1");
    } else {
        assetStreamer_.stop();
    }

    asyncPrefetchQueued_ = 0U;

    if (!flushPendingUploads()) {
        logError(
            "static mesh batched texture upload failed");
        shutdown();
        return false;
    }

    const auto mipRegistryStats =
        textureMipResidency_.stats();

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_TEXTURE_RESIDENCY_REGISTRY textures=%u degraded=%u resident_mb=%.2f requested_mb=%.2f",
        static_cast<unsigned int>(
            mipRegistryStats.textureCount),
        static_cast<unsigned int>(
            mipRegistryStats.
                degradedTextureCount),
        static_cast<double>(
            mipRegistryStats.
                residentBytes) /
            (1024.0 * 1024.0),
        static_cast<double>(
            mipRegistryStats.
                requestedBytes) /
            (1024.0 * 1024.0));

    if (streamGraphReady_) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_STREAM_RESOURCE_DECISION_INDEX_READY bindings=%u unique=%u",
            static_cast<unsigned int>(
                streamGraph_.bindingCount()),
            static_cast<unsigned int>(
                streamGraph_.uniqueResourceCount()));
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STATIC_MATERIAL_DEDUP batches=%u unique=%u reused=%u descriptor_sets=%u",
        static_cast<unsigned int>(
            asset.batches.size()),
        static_cast<unsigned int>(
            materials_.size()),
        static_cast<unsigned int>(
            reusedMaterialCount),
        static_cast<unsigned int>(
            materials_.size() *
            kDescriptorFrames));

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_PBR_MATERIALS_READY materials=%u pbr=%u legacy=%u normal=%u orm=%u emissive=%u photo_pbr=%u photo_detail=%u textures=%u",
        static_cast<unsigned int>(materials_.size()),
        static_cast<unsigned int>(pbrMaterialCount),
        static_cast<unsigned int>(materials_.size() - pbrMaterialCount),
        static_cast<unsigned int>(normalMapCount),
        static_cast<unsigned int>(ormMapCount),
        static_cast<unsigned int>(emissiveMapCount),
        static_cast<unsigned int>(photogrammetryPbrCount),
        static_cast<unsigned int>(photoDetailMapCount),
        static_cast<unsigned int>(textures_.size()));

    try {
        materialVisibilityStates_.assign(
            materials_.size(),
            0U);
        materialVisibilityGenerations_.assign(
            materials_.size(),
            0U);
        materialVisibilityGeneration_ = 1U;
    } catch (...) {
        logError(
            "static mesh material visibility cache allocation failed");
        shutdown();
        return false;
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_MATERIAL_VISIBILITY_GENERATION_CACHE_READY materials=%u",
        static_cast<unsigned int>(
            materials_.size()));

    if (!createGeometryResidency(
            asset,
            batchMaterialIndices)) {
        logError(
            "Sanctum consolidated geometry upload failed");
        shutdown();
        return false;
    }

    if (!createIndirectDrawBuffers()) {
        logError(
            "static draw submission scratch allocation failed");
        shutdown();
        return false;
    }

    totalVertices_ =
        asset.totalVertices;
    totalIndices_ =
        asset.totalIndices;
    ready_ =
        !batches_.empty() &&
        !materials_.empty() &&
        !textures_.empty();

    if (ready_) {
        logInfo(
            "XZIEL_VERTEX_TRANSFORM_PRECOMPUTE_READY");

        if (modelPath.find("/weapons/") !=
            std::string::npos) {
            logInfo("XZIEL_WEAPON_VIEWMODEL_READY");
        } else {
            logInfo("XZIEL_SANCTUM_MESH_READY");
        }
    }

    return ready_;
}

void VulkanStaticMeshRenderer::shutdown() noexcept {
    ready_ = false;

    assetStreamer_.stop();
    asyncPrefetchQueued_ = 0U;

    if (device_ != VK_NULL_HANDLE) {
        // Initialization failures can leave recorded-but-unsubmitted uploads.
        // Drop those command/staging resources before destroying their images.
        discardPendingUploads();

        destroyRuntimeTextureUpload();
        destroyGeometryResidency();

        for (auto& texture : textures_) {
            destroyTexture(texture);
        }

        if (pipeline_ != VK_NULL_HANDLE) {
            vkDestroyPipeline(
                device_,
                pipeline_,
                nullptr);
        }

        if (pipelineDoubleSided_ != VK_NULL_HANDLE) {
            vkDestroyPipeline(
                device_,
                pipelineDoubleSided_,
                nullptr);
        }

        if (pipelineLayout_ != VK_NULL_HANDLE) {
            vkDestroyPipelineLayout(
                device_,
                pipelineLayout_,
                nullptr);
        }

        if (descriptorPool_ != VK_NULL_HANDLE) {
            vkDestroyDescriptorPool(
                device_,
                descriptorPool_,
                nullptr);
        }

        if (descriptorSetLayout_ != VK_NULL_HANDLE) {
            vkDestroyDescriptorSetLayout(
                device_,
                descriptorSetLayout_,
                nullptr);
        }
    }

    batches_.clear();
    materials_.clear();
    materialVisibilityStates_.clear();
    materialVisibilityGenerations_.clear();
    materialVisibilityGeneration_ = 1U;
    textures_.clear();

    streamGraph_.reset();
    textureMipResidency_.reset();
    streamGraphReady_ = false;
    geometryPortalReachable_.fill(0U);
    cachedPortalReachabilityCell_ = 0U;
    portalReachabilityCacheValid_ = false;
    streamFallbackTextureIndex_ = UINT32_MAX;
    runtimeTextureUpload_ = {};
    runtimeTextureTransitionFrame_ = 0U;
    streamResidencyProbeEnabled_ = false;
    streamResidencyProbeComplete_ = false;
    streamResidencyProbeReloadComplete_ = false;
    streamResidencyProbeTextureIndex_ =
        UINT32_MAX;
    streamResidencyProbeReloadFrame_ = 0U;
    geometryResidencyProbeEnabled_ = false;
    geometryResidencyProbeComplete_ = false;
    geometryResidencyProbeCellSlot_ = UINT32_MAX;
    geometryResidencyProbeReloadFrame_ = 0U;
    geometryDirectory_ = {};
    geometryAssetPath_.clear();
    streamCellBounds_ = {};
    streamDecisionCount_ = 0U;
    cachedStreamPlanStats_ = {};
    cachedStreamPlanCell_ = 0U;
    cachedStreamPlanPressure_ =
        MemoryPressure::Normal;
    cachedStreamColdBatches_ = 0U;
    streamPlanBuildCount_ = 0U;
    streamPlanCacheHitCount_ = 0U;
    streamCellHeatRefreshCount_ = 0U;
    streamPlanDirty_ = true;
    streamPlanFrame_ = 0U;
    lastLoggedStreamCell_ = 0U;
    pendingUploads_.clear();
    pendingUploadBytes_ = 0U;

    pipeline_ = VK_NULL_HANDLE;
    pipelineDoubleSided_ = VK_NULL_HANDLE;
    pipelineLayout_ = VK_NULL_HANDLE;
    descriptorPool_ = VK_NULL_HANDLE;
    descriptorSetLayout_ = VK_NULL_HANDLE;

    totalVertices_ = 0U;
    totalIndices_ = 0U;
    samplerAnisotropyEnabled_ = false;
    packedStaticVertexEnabled_ = false;
    astcLdrSupported_ = false;
    multiDrawIndirectEnabled_ = false;
    maxDrawIndirectCount_ = 1U;
    maxSamplerAnisotropy_ = 1.0f;
    uploadBatchCommandLimit_ = 16U;
    textureResidentBudgetBytes_ =
        128ULL * 1024ULL * 1024ULL;
    textureResidentBytes_ = 0U;
    textureDegradedCount_ = 0U;

    geometryResidentBudgetBytes_ =
        96ULL * 1024ULL * 1024ULL;
    geometryResidentBytes_ = 0U;

    physicalDevice_ = VK_NULL_HANDLE;
    device_ = VK_NULL_HANDLE;
    graphicsQueue_ = VK_NULL_HANDLE;
    graphicsQueueFamily_ = UINT32_MAX;
    commandPool_ = VK_NULL_HANDLE;
    renderPass_ = VK_NULL_HANDLE;
    sampleCount_ = VK_SAMPLE_COUNT_1_BIT;
}

bool VulkanStaticMeshRenderer::ready() const noexcept {
    return ready_;
}

std::uint32_t VulkanStaticMeshRenderer::batchCount() const noexcept {
    return static_cast<std::uint32_t>(
        batches_.size());
}

std::uint32_t VulkanStaticMeshRenderer::totalVertices() const noexcept {
    return totalVertices_;
}

std::uint32_t VulkanStaticMeshRenderer::totalIndices() const noexcept {
    return totalIndices_;
}

StaticMeshFrameStats
VulkanStaticMeshRenderer::frameStats() const noexcept {
    return frameStats_;
}

void VulkanStaticMeshRenderer::setStreamingPortalOpen(
    std::uint32_t portalId,
    bool open) noexcept {
    if (!streamGraphReady_ ||
        portalId == 0U) {
        return;
    }

    bool current = false;

    if (!streamGraph_.portalOpen(
            portalId,
            current) ||
        current == open) {
        return;
    }

    if (streamGraph_.setPortalOpen(
            portalId,
            open)) {
        streamPlanDirty_ = true;
        portalReachabilityCacheValid_ = false;
        streamCullLogged_ = false;
    }
}

void VulkanStaticMeshRenderer::cacheGpuBatchCullingSphere(
    GpuBatch& batch) noexcept {
    batch.cullCenterX =
        (batch.bounds.minimum[0] +
         batch.bounds.maximum[0]) *
        0.5f;
    batch.cullCenterY =
        (batch.bounds.minimum[1] +
         batch.bounds.maximum[1]) *
        0.5f;
    batch.cullCenterZ =
        (batch.bounds.minimum[2] +
         batch.bounds.maximum[2]) *
        0.5f;

    const float extentX =
        (batch.bounds.maximum[0] -
         batch.bounds.minimum[0]) *
        0.5f;
    const float extentY =
        (batch.bounds.maximum[1] -
         batch.bounds.minimum[1]) *
        0.5f;
    const float extentZ =
        (batch.bounds.maximum[2] -
         batch.bounds.minimum[2]) *
        0.5f;

    batch.cullRadius =
        std::sqrt(
            extentX * extentX +
            extentY * extentY +
            extentZ * extentZ);
}

void VulkanStaticMeshRenderer::rebuildStreamingCellBounds() noexcept {
    streamCellBounds_ = {};
    streamCellBoundsCount_ = 0U;

    for (const auto& batch : batches_) {
        if (batch.streamCellId == 0U) {
            continue;
        }

        StreamCellBounds* slot = nullptr;

        for (auto& candidate : streamCellBounds_) {
            if (candidate.valid &&
                candidate.cellId ==
                    batch.streamCellId) {
                slot = &candidate;
                break;
            }

            if (!candidate.valid &&
                slot == nullptr) {
                slot = &candidate;
            }
        }

        if (slot == nullptr) {
            continue;
        }

        if (!slot->valid) {
            slot->cellId =
                batch.streamCellId;
            slot->bounds =
                batch.bounds;
            slot->valid = true;
            ++streamCellBoundsCount_;
            continue;
        }

        for (std::size_t axis = 0U;
             axis < 3U;
             ++axis) {
            slot->bounds.minimum[axis] =
                std::min(
                    slot->bounds.minimum[axis],
                    batch.bounds.minimum[axis]);
            slot->bounds.maximum[axis] =
                std::max(
                    slot->bounds.maximum[axis],
                    batch.bounds.maximum[axis]);
        }
    }

    for (std::size_t boundsSlot = 0U;
         boundsSlot < streamCellBoundsCount_;
         ++boundsSlot) {
        auto& cell =
            streamCellBounds_[boundsSlot];

        cell.cullCenterX =
            (cell.bounds.minimum[0] +
             cell.bounds.maximum[0]) *
            0.5f;
        cell.cullCenterY =
            (cell.bounds.minimum[1] +
             cell.bounds.maximum[1]) *
            0.5f;
        cell.cullCenterZ =
            (cell.bounds.minimum[2] +
             cell.bounds.maximum[2]) *
            0.5f;

        const float extentX =
            (cell.bounds.maximum[0] -
             cell.bounds.minimum[0]) *
            0.5f;
        const float extentY =
            (cell.bounds.maximum[1] -
             cell.bounds.minimum[1]) *
            0.5f;
        const float extentZ =
            (cell.bounds.maximum[2] -
             cell.bounds.minimum[2]) *
            0.5f;

        cell.cullRadius =
            std::sqrt(
                extentX * extentX +
                extentY * extentY +
                extentZ * extentZ);

        cell.volume =
            std::max(
                0.001f,
                cell.bounds.maximum[0] -
                    cell.bounds.minimum[0]) *
            std::max(
                0.001f,
                cell.bounds.maximum[1] -
                    cell.bounds.minimum[1]) *
            std::max(
                0.001f,
                cell.bounds.maximum[2] -
                    cell.bounds.minimum[2]);
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STREAM_CELL_VOLUME_CACHE_READY cells=%u",
        static_cast<unsigned int>(
            streamCellBoundsCount_));

    std::uint32_t indexedGeometryCells = 0U;

    for (std::size_t geometrySlot = 0U;
         geometrySlot < geometryCellCount_;
         ++geometrySlot) {
        auto& geometryCell =
            geometryCells_[geometrySlot];

        geometryCell.streamBoundsSlot =
            UINT32_MAX;

        if (geometryCell.cellId == 0U) {
            continue;
        }

        for (std::size_t boundsSlot = 0U;
             boundsSlot < streamCellBoundsCount_;
             ++boundsSlot) {
            const auto& bounds =
                streamCellBounds_[boundsSlot];

            if (bounds.valid &&
                bounds.cellId ==
                    geometryCell.cellId) {
                geometryCell.streamBoundsSlot =
                    static_cast<std::uint32_t>(
                        boundsSlot);
                ++indexedGeometryCells;
                break;
            }
        }

        std::uint32_t planCellSlot =
            UINT32_MAX;
        if (streamGraph_.resolveCellSlot(
                geometryCell.cellId,
                planCellSlot)) {
            geometryCell.streamPlanCellSlot =
                planCellSlot;
        } else {
            geometryCell.streamPlanCellSlot =
                UINT32_MAX;
        }
    }

    std::uint32_t indexedPlanCells = 0U;
    for (std::size_t geometrySlot = 0U;
         geometrySlot < geometryCellCount_;
         ++geometrySlot) {
        indexedPlanCells +=
            geometryCells_[geometrySlot].
                    streamPlanCellSlot !=
                UINT32_MAX
            ? 1U
            : 0U;
    }

    portalReachabilityCacheValid_ = false;
    cachedPortalReachabilityCell_ = 0U;
    geometryPortalReachable_.fill(0U);

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STREAM_CELL_BOUNDS_INDEX_READY indexed=%u geometry_cells=%u bounds=%u plan_slots=%u",
        static_cast<unsigned int>(
            indexedGeometryCells),
        static_cast<unsigned int>(
            geometryCellCount_),
        static_cast<unsigned int>(
            streamCellBoundsCount_),
        static_cast<unsigned int>(
            indexedPlanCells));

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STREAM_PLAN_CELL_SLOTS_READY indexed=%u geometry_cells=%u",
        static_cast<unsigned int>(
            indexedPlanCells),
        static_cast<unsigned int>(
            geometryCellCount_));
}

std::uint32_t VulkanStaticMeshRenderer::inferStreamingCell(
    const StaticMeshCameraState& camera) const noexcept {
    const std::array<float, 3> point{{
        camera.x,
        camera.y,
        camera.z,
    }};

    std::uint32_t bestCell = 0U;
    float bestDistance =
        std::numeric_limits<float>::infinity();
    float bestVolume =
        std::numeric_limits<float>::infinity();

    for (std::size_t boundsSlot = 0U;
         boundsSlot < streamCellBoundsCount_;
         ++boundsSlot) {
        const auto& cell =
            streamCellBounds_[boundsSlot];

        if (cell.cellId == 0U) {
            continue;
        }

        float distanceSquared = 0.0f;

        for (std::size_t axis = 0U;
             axis < 3U;
             ++axis) {
            const float minimum =
                cell.bounds.minimum[axis];
            const float maximum =
                cell.bounds.maximum[axis];

            if (point[axis] < minimum) {
                const float d =
                    minimum - point[axis];
                distanceSquared += d * d;
            } else if (
                point[axis] > maximum) {
                const float d =
                    point[axis] - maximum;
                distanceSquared += d * d;
            }
        }

        if (distanceSquared <
                bestDistance ||
            (distanceSquared ==
                 bestDistance &&
             cell.volume < bestVolume)) {
            bestDistance =
                distanceSquared;
            bestVolume =
                cell.volume;
            bestCell =
                cell.cellId;
        }
    }

    return bestCell;
}

const StreamCellResourceDecision*
VulkanStaticMeshRenderer::streamDecision(
    std::uint64_t resourceId,
    std::size_t count) const noexcept {
    if (resourceId == 0U) {
        return nullptr;
    }

    const std::size_t limit =
        std::min(
            count,
            streamDecisions_.size());

    for (std::size_t i = 0U;
         i < limit;
         ++i) {
        if (streamDecisions_[i].
                resourceId ==
            resourceId) {
            return &streamDecisions_[i];
        }
    }

    return nullptr;
}

const StreamCellResourceDecision*
VulkanStaticMeshRenderer::streamDecisionAt(
    std::uint32_t slot,
    std::uint64_t resourceId,
    std::size_t count) const noexcept {
    const std::size_t limit =
        std::min(
            count,
            streamDecisions_.size());

    if (slot < limit &&
        streamDecisions_[slot].
            resourceId ==
            resourceId) {
        return &streamDecisions_[slot];
    }

    return streamDecision(
        resourceId,
        count);
}

bool VulkanStaticMeshRenderer::updateTextureDescriptorForFrame(
    std::uint32_t textureIndex,
    std::uint32_t frameSlot,
    std::uint32_t replacementTextureIndex) noexcept {
    if (replacementTextureIndex >=
        textures_.size()) {
        return false;
    }

    return updateTextureDescriptorForFrame(
        textureIndex,
        frameSlot,
        textures_[replacementTextureIndex]);
}

bool VulkanStaticMeshRenderer::updateTextureDescriptorForFrame(
    std::uint32_t textureIndex,
    std::uint32_t frameSlot,
    const GpuTexture& replacement) noexcept {
    if (frameSlot >= kDescriptorFrames ||
        textureIndex >= textures_.size() ||
        !replacement.physicallyResident ||
        replacement.view == VK_NULL_HANDLE ||
        replacement.sampler == VK_NULL_HANDLE) {
        return false;
    }

    bool updatedAny = false;

    for (auto& material : materials_) {
        if (material.descriptorSets[frameSlot] ==
            VK_NULL_HANDLE) {
            continue;
        }

        const std::array<std::uint32_t, 4> indices{{
            material.albedoTextureIndex,
            material.normalTextureIndex,
            material.ormTextureIndex,
            material.emissiveTextureIndex,
        }};

        for (std::uint32_t binding = 0U;
             binding < indices.size();
             ++binding) {
            if (indices[binding] !=
                textureIndex) {
                continue;
            }

            VkDescriptorImageInfo image{};
            image.sampler =
                replacement.sampler;
            image.imageView =
                replacement.view;
            image.imageLayout =
                VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;

            VkWriteDescriptorSet write{
                VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET
            };
            write.dstSet =
                material.descriptorSets[frameSlot];
            write.dstBinding =
                binding;
            write.descriptorCount = 1U;
            write.descriptorType =
                VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
            write.pImageInfo =
                &image;

            vkUpdateDescriptorSets(
                device_,
                1U,
                &write,
                0U,
                nullptr);

            updatedAny = true;
        }
    }

    return updatedAny;
}

std::uint64_t VulkanStaticMeshRenderer::texturePayloadFromMip(
    const GpuTexture& texture,
    std::uint32_t baseMip) const noexcept {
    if (texture.sourceMipLevels == 0U) {
        return 0U;
    }

    baseMip =
        std::min<std::uint32_t>(
            baseMip,
            texture.sourceMipLevels - 1U);

    std::uint64_t total = 0U;

    for (std::uint32_t mip = baseMip;
         mip < texture.sourceMipLevels;
         ++mip) {
        const std::uint64_t value =
            texture.sourceMipBytes[mip];

        if (value >
            std::numeric_limits<std::uint64_t>::max() -
                total) {
            return
                std::numeric_limits<std::uint64_t>::max();
        }

        total += value;
    }

    return total;
}

bool VulkanStaticMeshRenderer::materialStreamingReady(
    const GpuMaterial& material,
    std::uint32_t frameSlot) const noexcept {
    if (frameSlot >= kDescriptorFrames) {
        return false;
    }

    const std::array<std::uint32_t, 4> indices{{
        material.albedoTextureIndex,
        material.normalTextureIndex,
        material.ormTextureIndex,
        material.emissiveTextureIndex,
    }};

    const std::uint8_t slotBit =
        static_cast<std::uint8_t>(
            1U << frameSlot);

    for (const auto textureIndex :
         indices) {
        if (textureIndex >=
            textures_.size()) {
            return false;
        }

        const auto& texture =
            textures_[textureIndex];

        if (!texture.physicallyResident ||
            (texture.descriptorResidentMask &
             slotBit) == 0U) {
            return false;
        }
    }

    return true;
}

void VulkanStaticMeshRenderer::releaseTextureGpuResidency(
    GpuTexture& texture) noexcept {
    if (device_ == VK_NULL_HANDLE) {
        texture.image = VK_NULL_HANDLE;
        texture.memory = VK_NULL_HANDLE;
        texture.view = VK_NULL_HANDLE;
        texture.sampler = VK_NULL_HANDLE;
        texture.physicallyResident = false;
        texture.descriptorResidentMask = 0U;
        return;
    }

    if (texture.residentPayloadBytes <=
        textureResidentBytes_) {
        textureResidentBytes_ -=
            texture.residentPayloadBytes;
    } else {
        textureResidentBytes_ = 0U;
    }

    if (texture.sampler != VK_NULL_HANDLE) {
        vkDestroySampler(
            device_,
            texture.sampler,
            nullptr);
    }

    if (texture.view != VK_NULL_HANDLE) {
        vkDestroyImageView(
            device_,
            texture.view,
            nullptr);
    }

    if (texture.image != VK_NULL_HANDLE) {
        vkDestroyImage(
            device_,
            texture.image,
            nullptr);
    }

    if (texture.memory != VK_NULL_HANDLE) {
        vkFreeMemory(
            device_,
            texture.memory,
            nullptr);
    }

    texture.image = VK_NULL_HANDLE;
    texture.memory = VK_NULL_HANDLE;
    texture.view = VK_NULL_HANDLE;
    texture.sampler = VK_NULL_HANDLE;
    texture.residentWidth = 0U;
    texture.residentHeight = 0U;
    texture.mipLevels = 0U;
    texture.residentPayloadBytes = 0U;
    texture.allocationBytes = 0U;
    texture.physicallyResident = false;
    texture.descriptorResidentMask = 0U;
}

void VulkanStaticMeshRenderer::destroyRuntimeTextureUpload() noexcept {
    if (!runtimeTextureUpload_.active) {
        runtimeTextureUpload_ = {};
        return;
    }

    if (device_ != VK_NULL_HANDLE &&
        runtimeTextureUpload_.fence !=
            VK_NULL_HANDLE) {
        const VkResult fenceStatus =
            vkGetFenceStatus(
                device_,
                runtimeTextureUpload_.fence);

        // Blocking is allowed only during shutdown. A runtime device/fence
        // error must never turn into an infinite wait on the render thread.
        if (fenceStatus == VK_NOT_READY &&
            !ready_) {
            (void) vkWaitForFences(
                device_,
                1U,
                &runtimeTextureUpload_.fence,
                VK_TRUE,
                UINT64_MAX);
        }
    }

    if (device_ != VK_NULL_HANDLE) {
        if (runtimeTextureUpload_.command !=
            VK_NULL_HANDLE &&
            commandPool_ != VK_NULL_HANDLE) {
            vkFreeCommandBuffers(
                device_,
                commandPool_,
                1U,
                &runtimeTextureUpload_.command);
        }

        if (runtimeTextureUpload_.stagingBuffer !=
            VK_NULL_HANDLE) {
            vkDestroyBuffer(
                device_,
                runtimeTextureUpload_.stagingBuffer,
                nullptr);
        }

        if (runtimeTextureUpload_.stagingMemory !=
            VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                runtimeTextureUpload_.stagingMemory,
                nullptr);
        }

        if (runtimeTextureUpload_.fence !=
            VK_NULL_HANDLE) {
            vkDestroyFence(
                device_,
                runtimeTextureUpload_.fence,
                nullptr);
        }

        destroyTexture(
            runtimeTextureUpload_.replacement);
    }

    runtimeTextureUpload_ = {};
}

bool VulkanStaticMeshRenderer::queueRuntimeTextureReplacement(
    AAssetManager* assetManager,
    const char* sourceTextureAssetPath,
    const char* replacementAssetPath) noexcept {
    if (!ready_ ||
        assetManager == nullptr ||
        sourceTextureAssetPath == nullptr ||
        replacementAssetPath == nullptr ||
        sourceTextureAssetPath[0] == '\0' ||
        replacementAssetPath[0] == '\0' ||
        runtimeTextureUpload_.active) {
        return false;
    }

    std::uint32_t textureIndex = UINT32_MAX;

    for (std::uint32_t i = 0U;
         i < textures_.size();
         ++i) {
        if (textures_[i].assetPath ==
            sourceTextureAssetPath) {
            textureIndex = i;
            break;
        }
    }

    if (textureIndex == UINT32_MAX) {
        __android_log_print(
            ANDROID_LOG_WARN,
            kTag,
            "XZIEL_AD_TEXTURE_SOURCE_NOT_FOUND source=%s",
            sourceTextureAssetPath);
        return false;
    }

    AAsset* asset =
        AAssetManager_open(
            assetManager,
            replacementAssetPath,
            AASSET_MODE_BUFFER);

    if (asset == nullptr) {
        __android_log_print(
            ANDROID_LOG_WARN,
            kTag,
            "XZIEL_AD_TEXTURE_CREATIVE_NOT_FOUND replacement=%s",
            replacementAssetPath);
        return false;
    }

    const off_t length =
        AAsset_getLength(asset);

    if (length <= 0 ||
        static_cast<std::uint64_t>(length) >
            64ULL * 1024ULL * 1024ULL) {
        AAsset_close(asset);
        return false;
    }

    std::vector<std::byte> bytes;

    try {
        bytes.resize(
            static_cast<std::size_t>(
                length));
    } catch (...) {
        AAsset_close(asset);
        return false;
    }

    const int read =
        AAsset_read(
            asset,
            bytes.data(),
            bytes.size());

    AAsset_close(asset);

    if (read < 0 ||
        static_cast<std::size_t>(read) !=
            bytes.size()) {
        return false;
    }

    if (!beginRuntimeKtx2Upload(
            textureIndex,
            0U,
            std::move(bytes))) {
        __android_log_print(
            ANDROID_LOG_WARN,
            kTag,
            "XZIEL_AD_TEXTURE_UPLOAD_REJECTED texture=%u source=%s replacement=%s",
            static_cast<unsigned int>(
                textureIndex),
            sourceTextureAssetPath,
            replacementAssetPath);
        return false;
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_AD_TEXTURE_UPLOAD_SUBMITTED texture=%u source=%s replacement=%s",
        static_cast<unsigned int>(
            textureIndex),
        sourceTextureAssetPath,
        replacementAssetPath);

    return true;
}

bool VulkanStaticMeshRenderer::runtimeTextureReplacementBusy() const noexcept {
    return runtimeTextureUpload_.active;
}

bool VulkanStaticMeshRenderer::beginRuntimeKtx2Upload(
    std::uint32_t textureIndex,
    std::uint32_t targetBaseMip,
    std::vector<std::byte>&& bytes) noexcept {
    if (runtimeTextureUpload_.active ||
        textureIndex >= textures_.size() ||
        bytes.empty() ||
        device_ == VK_NULL_HANDLE) {
        return false;
    }

    const auto& sourceTexture =
        textures_[textureIndex];

    Ktx2Texture parsedTexture{};
    const auto parsed =
        parseKtx2Astc(
            std::span<const std::byte>(
                bytes.data(),
                bytes.size()),
            parsedTexture);

    if (!parsed.success ||
        parsedTexture.levels.empty() ||
        parsedTexture.srgb !=
            sourceTexture.srgb ||
        parsedTexture.levels.size() >
            kMaxStreamedTextureMips) {
        return false;
    }

    targetBaseMip =
        std::min<std::uint32_t>(
            targetBaseMip,
            static_cast<std::uint32_t>(
                parsedTexture.levels.size() -
                1U));

    const auto residentRange =
        planKtx2ResidentMipRange(
            parsedTexture,
            targetBaseMip);

    if (!residentRange.valid) {
        return false;
    }

    const VkFormat textureFormat =
        static_cast<VkFormat>(
            parsedTexture.vkFormat);

    VkFormatProperties properties{};
    vkGetPhysicalDeviceFormatProperties(
        physicalDevice_,
        textureFormat,
        &properties);

    if ((properties.optimalTilingFeatures &
         VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT) == 0U) {
        return false;
    }

    std::vector<VkDeviceSize> stagingOffsets;
    std::vector<VkBufferImageCopy> regions;
    VkDeviceSize stagingBytes = 0U;

    try {
        stagingOffsets.reserve(
            residentRange.mipCount);
        regions.reserve(
            residentRange.mipCount);

        for (std::size_t sourceMip =
                 targetBaseMip;
             sourceMip <
                 parsedTexture.levels.size();
             ++sourceMip) {
            const auto& level =
                parsedTexture.levels[
                    sourceMip];

            stagingBytes =
                (stagingBytes + 15U) &
                ~VkDeviceSize{15U};

            stagingOffsets.push_back(
                stagingBytes);

            if (level.byteLength >
                std::numeric_limits<
                    VkDeviceSize>::max() -
                    stagingBytes) {
                return false;
            }

            stagingBytes +=
                static_cast<VkDeviceSize>(
                    level.byteLength);
        }
    } catch (...) {
        return false;
    }

    if (stagingBytes == 0U) {
        return false;
    }

    RuntimeTextureUpload upload{};
    upload.textureIndex =
        textureIndex;
    upload.targetBaseMip =
        targetBaseMip;

    if (!createBuffer(
            stagingBytes,
            VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
            upload.stagingBuffer,
            upload.stagingMemory)) {
        return false;
    }

    auto cleanup =
        [&]() noexcept {
            if (upload.command !=
                    VK_NULL_HANDLE &&
                commandPool_ !=
                    VK_NULL_HANDLE) {
                vkFreeCommandBuffers(
                    device_,
                    commandPool_,
                    1U,
                    &upload.command);
            }
            if (upload.stagingBuffer !=
                VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    upload.stagingBuffer,
                    nullptr);
            }
            if (upload.stagingMemory !=
                VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    upload.stagingMemory,
                    nullptr);
            }
            if (upload.fence !=
                VK_NULL_HANDLE) {
                vkDestroyFence(
                    device_,
                    upload.fence,
                    nullptr);
            }
            destroyTexture(
                upload.replacement);
        };

    void* mapped = nullptr;

    if (!ok(
            vkMapMemory(
                device_,
                upload.stagingMemory,
                0U,
                stagingBytes,
                0U,
                &mapped))) {
        cleanup();
        return false;
    }

    auto* destination =
        static_cast<std::byte*>(mapped);

    for (std::size_t sourceMip =
             targetBaseMip;
         sourceMip <
             parsedTexture.levels.size();
         ++sourceMip) {
        const std::size_t residentMip =
            sourceMip -
            targetBaseMip;
        const auto& level =
            parsedTexture.levels[
                sourceMip];

        std::memcpy(
            destination +
                stagingOffsets[
                    residentMip],
            bytes.data() +
                static_cast<std::size_t>(
                    level.byteOffset),
            static_cast<std::size_t>(
                level.byteLength));

        VkBufferImageCopy copy{};
        copy.bufferOffset =
            stagingOffsets[
                residentMip];
        copy.imageSubresource.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        copy.imageSubresource.mipLevel =
            static_cast<std::uint32_t>(
                residentMip);
        copy.imageSubresource.layerCount =
            1U;
        copy.imageExtent = {
            level.width,
            level.height,
            1U,
        };

        regions.push_back(copy);
    }

    vkUnmapMemory(
        device_,
        upload.stagingMemory);

    VkImageCreateInfo imageInfo{
        VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO
    };
    imageInfo.imageType =
        VK_IMAGE_TYPE_2D;
    imageInfo.extent = {
        residentRange.width,
        residentRange.height,
        1U,
    };
    imageInfo.mipLevels =
        residentRange.mipCount;
    imageInfo.arrayLayers = 1U;
    imageInfo.format =
        textureFormat;
    imageInfo.tiling =
        VK_IMAGE_TILING_OPTIMAL;
    imageInfo.initialLayout =
        VK_IMAGE_LAYOUT_UNDEFINED;
    imageInfo.usage =
        VK_IMAGE_USAGE_TRANSFER_DST_BIT |
        VK_IMAGE_USAGE_SAMPLED_BIT;
    imageInfo.samples =
        VK_SAMPLE_COUNT_1_BIT;
    imageInfo.sharingMode =
        VK_SHARING_MODE_EXCLUSIVE;

    if (!ok(
            vkCreateImage(
                device_,
                &imageInfo,
                nullptr,
                &upload.replacement.image))) {
        cleanup();
        return false;
    }

    VkMemoryRequirements requirements{};
    vkGetImageMemoryRequirements(
        device_,
        upload.replacement.image,
        &requirements);

    std::uint32_t memoryType = 0U;

    if (!findMemoryType(
            requirements.memoryTypeBits,
            VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
            memoryType)) {
        cleanup();
        return false;
    }

    VkMemoryAllocateInfo allocation{
        VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO
    };
    allocation.allocationSize =
        requirements.size;
    allocation.memoryTypeIndex =
        memoryType;

    if (!ok(
            vkAllocateMemory(
                device_,
                &allocation,
                nullptr,
                &upload.replacement.memory)) ||
        !ok(
            vkBindImageMemory(
                device_,
                upload.replacement.image,
                upload.replacement.memory,
                0U))) {
        cleanup();
        return false;
    }

    upload.command =
        beginUploadCommands();

    if (upload.command ==
        VK_NULL_HANDLE) {
        cleanup();
        return false;
    }

    VkImageMemoryBarrier toTransfer{
        VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
    };
    toTransfer.oldLayout =
        VK_IMAGE_LAYOUT_UNDEFINED;
    toTransfer.newLayout =
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    toTransfer.srcQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toTransfer.dstQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toTransfer.image =
        upload.replacement.image;
    toTransfer.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    toTransfer.subresourceRange.levelCount =
        imageInfo.mipLevels;
    toTransfer.subresourceRange.layerCount =
        1U;
    toTransfer.dstAccessMask =
        VK_ACCESS_TRANSFER_WRITE_BIT;

    vkCmdPipelineBarrier(
        upload.command,
        VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
        VK_PIPELINE_STAGE_TRANSFER_BIT,
        0U,
        0U, nullptr,
        0U, nullptr,
        1U, &toTransfer);

    vkCmdCopyBufferToImage(
        upload.command,
        upload.stagingBuffer,
        upload.replacement.image,
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
        static_cast<std::uint32_t>(
            regions.size()),
        regions.data());

    VkImageMemoryBarrier toShader{
        VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
    };
    toShader.oldLayout =
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    toShader.newLayout =
        VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    toShader.srcQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toShader.dstQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toShader.image =
        upload.replacement.image;
    toShader.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    toShader.subresourceRange.levelCount =
        imageInfo.mipLevels;
    toShader.subresourceRange.layerCount =
        1U;
    toShader.srcAccessMask =
        VK_ACCESS_TRANSFER_WRITE_BIT;
    toShader.dstAccessMask =
        VK_ACCESS_SHADER_READ_BIT;

    vkCmdPipelineBarrier(
        upload.command,
        VK_PIPELINE_STAGE_TRANSFER_BIT,
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
        0U,
        0U, nullptr,
        0U, nullptr,
        1U, &toShader);

    if (!ok(
            vkEndCommandBuffer(
                upload.command))) {
        cleanup();
        return false;
    }

    VkImageViewCreateInfo viewInfo{
        VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
    };
    viewInfo.image =
        upload.replacement.image;
    viewInfo.viewType =
        VK_IMAGE_VIEW_TYPE_2D;
    viewInfo.format =
        textureFormat;
    viewInfo.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.levelCount =
        imageInfo.mipLevels;
    viewInfo.subresourceRange.layerCount =
        1U;

    if (!ok(
            vkCreateImageView(
                device_,
                &viewInfo,
                nullptr,
                &upload.replacement.view)) ||
        !createTextureSampler(
            imageInfo.mipLevels,
            upload.replacement)) {
        cleanup();
        return false;
    }

    VkFenceCreateInfo fenceInfo{
        VK_STRUCTURE_TYPE_FENCE_CREATE_INFO
    };

    if (!ok(
            vkCreateFence(
                device_,
                &fenceInfo,
                nullptr,
                &upload.fence))) {
        cleanup();
        return false;
    }

    VkSubmitInfo submit{
        VK_STRUCTURE_TYPE_SUBMIT_INFO
    };
    submit.commandBufferCount = 1U;
    submit.pCommandBuffers =
        &upload.command;

    if (!ok(
            vkQueueSubmit(
                graphicsQueue_,
                1U,
                &submit,
                upload.fence))) {
        cleanup();
        return false;
    }

    upload.replacement.assetPath =
        sourceTexture.assetPath;
    upload.replacement.streamResourceId =
        sourceTexture.streamResourceId;
    upload.replacement.streamDecisionSlot =
        sourceTexture.streamDecisionSlot;
    upload.replacement.width =
        parsedTexture.width;
    upload.replacement.height =
        parsedTexture.height;
    upload.replacement.residentWidth =
        residentRange.width;
    upload.replacement.residentHeight =
        residentRange.height;
    upload.replacement.mipLevels =
        residentRange.mipCount;
    upload.replacement.residentBaseMip =
        targetBaseMip;
    upload.replacement.sourceMipLevels =
        static_cast<std::uint32_t>(
            parsedTexture.levels.size());
    upload.replacement.sourceMipBytes.fill(
        0U);

    for (std::uint32_t mip = 0U;
         mip <
             upload.replacement.
                 sourceMipLevels;
         ++mip) {
        upload.replacement.
            sourceMipBytes[mip] =
            parsedTexture.levels[mip].
                byteLength;
    }

    upload.replacement.residentPayloadBytes =
        residentRange.payloadBytes;
    upload.replacement.allocationBytes =
        static_cast<std::uint64_t>(
            requirements.size);
    upload.replacement.srgb =
        sourceTexture.srgb;
    upload.replacement.physicallyResident =
        true;
    upload.replacement.runtimeLoadQueued =
        false;
    upload.replacement.descriptorResidentMask =
        0U;

    upload.active = true;
    runtimeTextureUpload_ =
        std::move(upload);

    return true;
}

void VulkanStaticMeshRenderer::serviceRuntimeTextureResidency(
    std::uint32_t frameSlot,
    MemoryPressure memoryPressure) noexcept {
    if (frameSlot >= kDescriptorFrames) {
        return;
    }

    ++runtimeTextureTransitionFrame_;

    if (runtimeTextureUpload_.active) {
        auto& upload =
            runtimeTextureUpload_;

        if (!upload.uploadComplete) {
            const VkResult status =
                vkGetFenceStatus(
                    device_,
                    upload.fence);

            if (status == VK_SUCCESS) {
                if (upload.command !=
                        VK_NULL_HANDLE &&
                    commandPool_ !=
                        VK_NULL_HANDLE) {
                    vkFreeCommandBuffers(
                        device_,
                        commandPool_,
                        1U,
                        &upload.command);
                    upload.command =
                        VK_NULL_HANDLE;
                }

                if (upload.stagingBuffer !=
                    VK_NULL_HANDLE) {
                    vkDestroyBuffer(
                        device_,
                        upload.stagingBuffer,
                        nullptr);
                    upload.stagingBuffer =
                        VK_NULL_HANDLE;
                }

                if (upload.stagingMemory !=
                    VK_NULL_HANDLE) {
                    vkFreeMemory(
                        device_,
                        upload.stagingMemory,
                        nullptr);
                    upload.stagingMemory =
                        VK_NULL_HANDLE;
                }

                if (upload.fence !=
                    VK_NULL_HANDLE) {
                    vkDestroyFence(
                        device_,
                        upload.fence,
                        nullptr);
                    upload.fence =
                        VK_NULL_HANDLE;
                }

                upload.uploadComplete =
                    true;

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_RUNTIME_TEXTURE_UPLOAD_READY texture=%u base_mip=%u payload_kb=%.1f",
                    static_cast<unsigned int>(
                        upload.textureIndex),
                    static_cast<unsigned int>(
                        upload.replacement.
                            residentBaseMip),
                    static_cast<double>(
                        upload.replacement.
                            residentPayloadBytes) /
                        1024.0);
            } else if (
                status != VK_NOT_READY) {
                const std::uint32_t textureIndex =
                    upload.textureIndex;

                destroyRuntimeTextureUpload();

                if (textureIndex <
                    textures_.size()) {
                    textures_[textureIndex].
                        runtimeLoadQueued = false;
                }

                return;
            } else {
                return;
            }
        }

        const std::uint32_t textureIndex =
            upload.textureIndex;

        if (textureIndex >=
            textures_.size()) {
            destroyRuntimeTextureUpload();
            return;
        }

        const std::uint8_t slotBit =
            static_cast<std::uint8_t>(
                1U << frameSlot);

        if ((upload.descriptorSwapMask &
             slotBit) == 0U) {
            if (updateTextureDescriptorForFrame(
                    textureIndex,
                    frameSlot,
                    upload.replacement)) {
                upload.descriptorSwapMask |=
                    slotBit;

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_RUNTIME_TEXTURE_SWAP_SLOT texture=%u frame_slot=%u mask=%u target_base_mip=%u",
                    static_cast<unsigned int>(
                        textureIndex),
                    static_cast<unsigned int>(
                        frameSlot),
                    static_cast<unsigned int>(
                        upload.descriptorSwapMask),
                    static_cast<unsigned int>(
                        upload.targetBaseMip));
            }

            return;
        }

        const std::uint8_t fullMask =
            static_cast<std::uint8_t>(
                (1U << kDescriptorFrames) -
                1U);

        if (upload.descriptorSwapMask !=
            fullMask) {
            return;
        }

        auto& oldTexture =
            textures_[textureIndex];

        const bool oldWasResident =
            oldTexture.physicallyResident;
        const std::uint32_t oldBaseMip =
            oldTexture.residentBaseMip;
        const std::uint64_t oldPayloadBytes =
            oldTexture.residentPayloadBytes;

        if (oldWasResident) {
            releaseTextureGpuResidency(
                oldTexture);
        }

        auto replacement =
            std::move(upload.replacement);

        replacement.runtimeLoadQueued =
            false;
        replacement.descriptorResidentMask =
            fullMask;

        textures_[textureIndex] =
            std::move(replacement);

        if (textures_[textureIndex].
                residentPayloadBytes <=
            std::numeric_limits<
                std::uint64_t>::max() -
                textureResidentBytes_) {
            textureResidentBytes_ +=
                textures_[textureIndex].
                    residentPayloadBytes;
        }

        (void) textureMipResidency_.
            applyResidentBaseMip(
                textures_[textureIndex].
                    streamResourceId,
                textures_[textureIndex].
                    residentBaseMip,
                runtimeTextureTransitionFrame_);

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_RUNTIME_TEXTURE_SWAP_COMPLETE texture=%u old_base_mip=%u new_base_mip=%u old_payload_kb=%.1f new_payload_kb=%.1f mask=%u",
            static_cast<unsigned int>(
                textureIndex),
            static_cast<unsigned int>(
                oldBaseMip),
            static_cast<unsigned int>(
                textures_[textureIndex].
                    residentBaseMip),
            static_cast<double>(
                oldPayloadBytes) /
                1024.0,
            static_cast<double>(
                textures_[textureIndex].
                    residentPayloadBytes) /
                1024.0,
            static_cast<unsigned int>(
                textures_[textureIndex].
                    descriptorResidentMask));

        if (streamResidencyProbeEnabled_ &&
            !streamResidencyProbeComplete_ &&
            streamResidencyProbeTextureIndex_ ==
                textureIndex) {
            if (!streamResidencyProbeReloadComplete_ &&
                !oldWasResident) {
                streamResidencyProbeReloadComplete_ =
                    true;

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_RUNTIME_TEXTURE_RELOAD_COMPLETE texture=%u base_mip=%u mask=%u",
                    static_cast<unsigned int>(
                        textureIndex),
                    static_cast<unsigned int>(
                        textures_[textureIndex].
                            residentBaseMip),
                    static_cast<unsigned int>(
                        textures_[textureIndex].
                            descriptorResidentMask));
            } else if (
                streamResidencyProbeReloadComplete_ &&
                oldWasResident &&
                oldBaseMip > 0U &&
                textures_[textureIndex].
                    residentBaseMip == 0U) {
                streamResidencyProbeComplete_ =
                    true;

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_RUNTIME_TEXTURE_MIP_PROMOTION_COMPLETE texture=%u old_base_mip=%u new_base_mip=0 mask=%u",
                    static_cast<unsigned int>(
                        textureIndex),
                    static_cast<unsigned int>(
                        oldBaseMip),
                    static_cast<unsigned int>(
                        textures_[textureIndex].
                            descriptorResidentMask));
            }
        }

        runtimeTextureUpload_ = {};
        return;
    }

    // Intrinsic ad texture replacement must also work on maps that do not use
    // the Sanctum streaming graph. The remainder of this function is strictly
    // streaming-residency policy.
    if (!streamGraphReady_ ||
        streamFallbackTextureIndex_ >=
            textures_.size()) {
        return;
    }

    const std::uint8_t slotBit =
        static_cast<std::uint8_t>(
            1U << frameSlot);

    const std::uint32_t minimumStableFrames =
        geometryResidencyProbeEnabled_
        ? 8U
        : memoryPressure ==
              MemoryPressure::Critical
          ? 8U
          : memoryPressure ==
                MemoryPressure::Elevated
            ? 30U
            : 120U;

    for (std::uint32_t textureIndex = 0U;
         textureIndex < textures_.size();
         ++textureIndex) {
        if (textureIndex ==
                streamFallbackTextureIndex_) {
            continue;
        }

        auto& texture =
            textures_[textureIndex];

        const auto* decision =
            streamDecisionAt(
                texture.streamDecisionSlot,
                texture.streamResourceId,
                streamDecisionCount_);

        if (decision == nullptr) {
            continue;
        }

        const bool probeWantsResident =
            streamResidencyProbeEnabled_ &&
            !streamResidencyProbeComplete_ &&
            streamResidencyProbeTextureIndex_ ==
                textureIndex &&
            runtimeTextureTransitionFrame_ >=
                streamResidencyProbeReloadFrame_;

        const bool wantsResident =
            decision->desiredResident ||
            probeWantsResident;

        if (texture.physicallyResident &&
            wantsResident) {
            if ((texture.
                     descriptorResidentMask &
                 slotBit) == 0U) {
                if (updateTextureDescriptorForFrame(
                        textureIndex,
                        frameSlot,
                        textureIndex)) {
                    texture.
                        descriptorResidentMask |=
                        slotBit;

                    __android_log_print(
                        ANDROID_LOG_INFO,
                        kTag,
                        "XZIEL_RUNTIME_TEXTURE_DESCRIPTOR_RESTORE texture=%u frame_slot=%u mask=%u",
                        static_cast<unsigned int>(
                            textureIndex),
                        static_cast<unsigned int>(
                            frameSlot),
                        static_cast<unsigned int>(
                            texture.
                                descriptorResidentMask));
                }
                return;
            }

            if (texture.sourceMipLevels == 0U ||
                texture.assetPath.size() < 5U ||
                texture.assetPath.substr(
                    texture.assetPath.size() - 5U) !=
                    ".ktx2") {
                continue;
            }

            std::uint32_t targetBaseMip =
                std::min<std::uint32_t>(
                    decision->desiredMipBias,
                    texture.sourceMipLevels - 1U);

            if (streamResidencyProbeEnabled_ &&
                streamResidencyProbeReloadComplete_ &&
                !streamResidencyProbeComplete_ &&
                streamResidencyProbeTextureIndex_ ==
                    textureIndex) {
                targetBaseMip = 0U;
            }

            // Promotions must fit the steady-state texture budget after the
            // old image retires. If full hot quality does not fit, choose the
            // highest-quality mip tail that does instead of overcommitting.
            if (targetBaseMip <
                texture.residentBaseMip) {
                const std::uint64_t currentPayload =
                    texture.residentPayloadBytes;

                while (targetBaseMip <
                       texture.residentBaseMip) {
                    const std::uint64_t targetPayload =
                        texturePayloadFromMip(
                            texture,
                            targetBaseMip);

                    const std::uint64_t steadyBytes =
                        currentPayload <=
                                textureResidentBytes_
                        ? textureResidentBytes_ -
                              currentPayload
                        : 0U;

                    if (targetPayload <=
                        textureResidentBudgetBytes_ -
                            std::min(
                                textureResidentBudgetBytes_,
                                steadyBytes)) {
                        break;
                    }

                    ++targetBaseMip;
                }
            }

            if (targetBaseMip ==
                texture.residentBaseMip) {
                continue;
            }

            const bool promotion =
                targetBaseMip <
                texture.residentBaseMip;

            const std::uint32_t mipStableFrames =
                streamResidencyProbeEnabled_
                ? 8U
                : promotion
                  ? 8U
                  : memoryPressure ==
                        MemoryPressure::Critical
                    ? 8U
                    : memoryPressure ==
                          MemoryPressure::Elevated
                      ? 24U
                      : 45U;

            if (!streamCullingActive_ ||
                streamCellStableFrames_ <
                    mipStableFrames) {
                continue;
            }

            if (!texture.runtimeLoadQueued) {
                if (assetStreamer_.enqueue(
                        texture.assetPath)) {
                    texture.runtimeLoadQueued =
                        true;

                    __android_log_print(
                        ANDROID_LOG_INFO,
                        kTag,
                        "XZIEL_RUNTIME_TEXTURE_MIP_CHANGE_QUEUED texture=%u old_base_mip=%u new_base_mip=%u direction=%s path=%s",
                        static_cast<unsigned int>(
                            textureIndex),
                        static_cast<unsigned int>(
                            texture.residentBaseMip),
                        static_cast<unsigned int>(
                            targetBaseMip),
                        promotion
                            ? "promote"
                            : "demote",
                        texture.assetPath.c_str());
                }
                return;
            }

            bool finished = false;
            std::vector<std::byte> bytes;

            const bool success =
                assetStreamer_.tryTake(
                    texture.assetPath,
                    bytes,
                    finished);

            if (!finished) {
                return;
            }

            texture.runtimeLoadQueued =
                false;

            if (!success) {
                return;
            }

            if (beginRuntimeKtx2Upload(
                    textureIndex,
                    targetBaseMip,
                    std::move(bytes))) {
                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_RUNTIME_TEXTURE_MIP_CHANGE_SUBMITTED texture=%u old_base_mip=%u new_base_mip=%u direction=%s",
                    static_cast<unsigned int>(
                        textureIndex),
                    static_cast<unsigned int>(
                        texture.residentBaseMip),
                    static_cast<unsigned int>(
                        targetBaseMip),
                    promotion
                        ? "promote"
                        : "demote");
            }

            return;
        }

        if (texture.physicallyResident &&
            !wantsResident &&
            streamCullingActive_ &&
            streamCellStableFrames_ >=
                minimumStableFrames) {
            if ((texture.
                     descriptorResidentMask &
                 slotBit) != 0U) {
                if (updateTextureDescriptorForFrame(
                        textureIndex,
                        frameSlot,
                        streamFallbackTextureIndex_)) {
                    texture.
                        descriptorResidentMask &=
                        static_cast<std::uint8_t>(
                            ~slotBit);
                }
                return;
            }

            if (texture.
                    descriptorResidentMask ==
                0U) {
                const std::uint64_t freedBytes =
                    texture.
                        residentPayloadBytes;

                releaseTextureGpuResidency(
                    texture);

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_RUNTIME_TEXTURE_EVICTED texture=%u resource_id=%llu freed_kb=%.1f pressure=%u",
                    static_cast<unsigned int>(
                        textureIndex),
                    static_cast<unsigned long long>(
                        texture.
                            streamResourceId),
                    static_cast<double>(
                        freedBytes) /
                        1024.0,
                    static_cast<unsigned int>(
                        memoryPressure));

                if (streamResidencyProbeEnabled_ &&
                    !streamResidencyProbeComplete_ &&
                    streamResidencyProbeTextureIndex_ ==
                        UINT32_MAX) {
                    streamResidencyProbeTextureIndex_ =
                        textureIndex;
                    streamResidencyProbeReloadFrame_ =
                        runtimeTextureTransitionFrame_ +
                        12U;

                    __android_log_print(
                        ANDROID_LOG_INFO,
                        kTag,
                        "XZIEL_RUNTIME_TEXTURE_RELOAD_PROBE_ARMED texture=%u reload_frame=%llu",
                        static_cast<unsigned int>(
                            textureIndex),
                        static_cast<unsigned long long>(
                            streamResidencyProbeReloadFrame_));
                }

                return;
            }

            continue;
        }

        if (!texture.physicallyResident &&
            wantsResident) {
            if (texture.assetPath.size() <
                    5U ||
                texture.assetPath.substr(
                    texture.assetPath.size() -
                        5U) != ".ktx2") {
                continue;
            }

            if (!texture.runtimeLoadQueued) {
                if (assetStreamer_.enqueue(
                        texture.assetPath)) {
                    texture.runtimeLoadQueued =
                        true;

                    __android_log_print(
                        ANDROID_LOG_INFO,
                        kTag,
                        "XZIEL_RUNTIME_TEXTURE_RELOAD_QUEUED texture=%u base_mip=%u path=%s",
                        static_cast<unsigned int>(
                            textureIndex),
                        static_cast<unsigned int>(
                            std::min<std::uint32_t>(
                                decision->
                                    desiredMipBias,
                                texture.
                                    sourceMipLevels >
                                        0U
                                    ? texture.
                                          sourceMipLevels -
                                          1U
                                    : 0U)),
                        texture.assetPath.c_str());
                }
                return;
            }

            bool finished = false;
            std::vector<std::byte> bytes;

            const bool success =
                assetStreamer_.tryTake(
                    texture.assetPath,
                    bytes,
                    finished);

            if (!finished) {
                return;
            }

            texture.runtimeLoadQueued =
                false;

            if (!success) {
                return;
            }

            const std::uint32_t targetBaseMip =
                std::min<std::uint32_t>(
                    decision->desiredMipBias,
                    texture.sourceMipLevels >
                            0U
                        ? texture.
                              sourceMipLevels -
                              1U
                        : 0U);

            if (beginRuntimeKtx2Upload(
                    textureIndex,
                    targetBaseMip,
                    std::move(bytes))) {
                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_RUNTIME_TEXTURE_UPLOAD_SUBMITTED texture=%u base_mip=%u",
                    static_cast<unsigned int>(
                        textureIndex),
                    static_cast<unsigned int>(
                        targetBaseMip));
            }

            return;
        }
    }
}

void VulkanStaticMeshRenderer::releaseGeometryCellGpuResidency(
    GeometryCellResidency& cell) noexcept {
    if (device_ != VK_NULL_HANDLE) {
        if (cell.restoreMappedIndices != nullptr &&
            cell.indexMemory != VK_NULL_HANDLE) {
            vkUnmapMemory(
                device_,
                cell.indexMemory);
            cell.restoreMappedIndices = nullptr;
        }

        if (cell.restoreMappedVertices != nullptr &&
            cell.vertexMemory != VK_NULL_HANDLE) {
            vkUnmapMemory(
                device_,
                cell.vertexMemory);
            cell.restoreMappedVertices = nullptr;
        }
        if (cell.indexBuffer != VK_NULL_HANDLE) {
            vkDestroyBuffer(
                device_,
                cell.indexBuffer,
                nullptr);
        }

        if (cell.indexMemory != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                cell.indexMemory,
                nullptr);
        }

        if (cell.vertexBuffer != VK_NULL_HANDLE) {
            vkDestroyBuffer(
                device_,
                cell.vertexBuffer,
                nullptr);
        }

        if (cell.vertexMemory != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                cell.vertexMemory,
                nullptr);
        }
    }

    const std::uint64_t bytes =
        static_cast<std::uint64_t>(
            cell.vertexBytes +
            cell.indexBytes);

    if (cell.physicallyResident) {
        geometryResidentBytes_ =
            bytes <= geometryResidentBytes_
            ? geometryResidentBytes_ - bytes
            : 0U;
    }

    cell.vertexBuffer = VK_NULL_HANDLE;
    cell.vertexMemory = VK_NULL_HANDLE;
    cell.indexBuffer = VK_NULL_HANDLE;
    cell.indexMemory = VK_NULL_HANDLE;
    cell.deviceLocalHostVisible = false;
    cell.physicallyResident = false;
    cell.retireMask = 0U;
    cell.restoreVertexCursor = 0U;
    cell.restoreIndexCursor = 0U;
    cell.restoreCopyFrames = 0U;
    cell.restorePrepared = false;
}

VulkanStaticMeshRenderer::GeometryRestoreResult
VulkanStaticMeshRenderer::restoreGeometryCellGpuResidency(
    GeometryCellResidency& cell,
    VkDeviceSize copyBudgetBytes) noexcept {
    if (cell.physicallyResident) {
        return GeometryRestoreResult::Complete;
    }

    if (device_ == VK_NULL_HANDLE ||
        copyBudgetBytes == 0U ||
        cell.vertexBytes == 0U ||
        cell.indexBytes == 0U ||
        cell.reloadVertexBytes.size() !=
            static_cast<std::size_t>(
                cell.vertexBytes) ||
        cell.reloadIndexBytes.size() !=
            static_cast<std::size_t>(
                cell.indexBytes)) {
        return GeometryRestoreResult::Failed;
    }

    const VkMemoryPropertyFlags hostFlags =
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
        VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
    const VkMemoryPropertyFlags preferredFlags =
        hostFlags |
        VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;

    const auto destroyPartial =
        [&]() noexcept {
            if (cell.restoreMappedIndices != nullptr &&
                cell.indexMemory != VK_NULL_HANDLE) {
                vkUnmapMemory(
                    device_,
                    cell.indexMemory);
            }

            if (cell.restoreMappedVertices != nullptr &&
                cell.vertexMemory != VK_NULL_HANDLE) {
                vkUnmapMemory(
                    device_,
                    cell.vertexMemory);
            }

            cell.restoreMappedVertices = nullptr;
            cell.restoreMappedIndices = nullptr;
            cell.restoreVertexCursor = 0U;
            cell.restoreIndexCursor = 0U;
            cell.restoreCopyFrames = 0U;
            cell.restorePrepared = false;

            if (cell.indexBuffer != VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    cell.indexBuffer,
                    nullptr);
                cell.indexBuffer =
                    VK_NULL_HANDLE;
            }

            if (cell.indexMemory != VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    cell.indexMemory,
                    nullptr);
                cell.indexMemory =
                    VK_NULL_HANDLE;
            }

            if (cell.vertexBuffer != VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    cell.vertexBuffer,
                    nullptr);
                cell.vertexBuffer =
                    VK_NULL_HANDLE;
            }

            if (cell.vertexMemory != VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    cell.vertexMemory,
                    nullptr);
                cell.vertexMemory =
                    VK_NULL_HANDLE;
            }
        };

    const auto createPair =
        [&](VkMemoryPropertyFlags flags) noexcept {
            if (!createBuffer(
                    cell.vertexBytes,
                    VK_BUFFER_USAGE_VERTEX_BUFFER_BIT |
                        VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                    flags,
                    cell.vertexBuffer,
                    cell.vertexMemory)) {
                return false;
            }

            if (!createBuffer(
                    cell.indexBytes,
                    VK_BUFFER_USAGE_INDEX_BUFFER_BIT |
                        VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                    flags,
                    cell.indexBuffer,
                    cell.indexMemory)) {
                destroyPartial();
                return false;
            }

            return true;
        };

    if (!cell.restorePrepared) {
        cell.deviceLocalHostVisible =
            createPair(preferredFlags);

        if (!cell.deviceLocalHostVisible &&
            !createPair(hostFlags)) {
            return GeometryRestoreResult::Failed;
        }

        if (!ok(
                vkMapMemory(
                    device_,
                    cell.vertexMemory,
                    0U,
                    cell.vertexBytes,
                    0U,
                    &cell.restoreMappedVertices)) ||
            !ok(
                vkMapMemory(
                    device_,
                    cell.indexMemory,
                    0U,
                    cell.indexBytes,
                    0U,
                    &cell.restoreMappedIndices))) {
            destroyPartial();
            return GeometryRestoreResult::Failed;
        }

        cell.restoreVertexCursor = 0U;
        cell.restoreIndexCursor = 0U;
        cell.restoreCopyFrames = 0U;
        cell.restorePrepared = true;

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_RUNTIME_GEOMETRY_GPU_RESTORE_BEGIN cell=%u total_mb=%.2f copy_budget_kb=%.1f",
            static_cast<unsigned int>(
                cell.cellId),
            static_cast<double>(
                static_cast<std::uint64_t>(
                    cell.vertexBytes +
                    cell.indexBytes)) /
                (1024.0 * 1024.0),
            static_cast<double>(
                copyBudgetBytes) /
                1024.0);

        // Keep Vulkan allocation/mapping separate from the first bulk copy so
        // one render frame never pays both costs for a newly hot cell.
        return GeometryRestoreResult::InProgress;
    }

    VkDeviceSize remainingBudget =
        copyBudgetBytes;

    const auto copySlice =
        [&](const std::vector<std::byte>& source,
            VkDeviceSize& cursor,
            void* mapped) noexcept {
            if (remainingBudget == 0U ||
                mapped == nullptr ||
                cursor >=
                    static_cast<VkDeviceSize>(
                        source.size())) {
                return;
            }

            const VkDeviceSize available =
                static_cast<VkDeviceSize>(
                    source.size()) -
                cursor;
            const VkDeviceSize amount =
                std::min(
                    available,
                    remainingBudget);

            std::memcpy(
                static_cast<std::byte*>(mapped) +
                    static_cast<std::size_t>(
                        cursor),
                source.data() +
                    static_cast<std::size_t>(
                        cursor),
                static_cast<std::size_t>(
                    amount));

            cursor += amount;
            remainingBudget -= amount;
        };

    copySlice(
        cell.reloadVertexBytes,
        cell.restoreVertexCursor,
        cell.restoreMappedVertices);

    copySlice(
        cell.reloadIndexBytes,
        cell.restoreIndexCursor,
        cell.restoreMappedIndices);

    ++cell.restoreCopyFrames;

    if (cell.restoreVertexCursor <
            cell.vertexBytes ||
        cell.restoreIndexCursor <
            cell.indexBytes) {
        return GeometryRestoreResult::InProgress;
    }

    vkUnmapMemory(
        device_,
        cell.indexMemory);
    vkUnmapMemory(
        device_,
        cell.vertexMemory);

    cell.restoreMappedVertices = nullptr;
    cell.restoreMappedIndices = nullptr;

    const std::uint32_t copyFrames =
        cell.restoreCopyFrames;

    cell.physicallyResident = true;
    cell.retireMask = 0U;
    cell.reloadActive = false;
    cell.reloadFailed = false;
    cell.reloadScanCursor = 0U;
    cell.reloadRanges = {};
    cell.reloadPendingCount = 0U;
    cell.reloadPeakPendingCount = 0U;
    cell.reloadPeakCopyBytesPerFrame = 0U;
    cell.reloadStartFrame = 0U;
    cell.reloadVertexBytes.clear();
    cell.reloadIndexBytes.clear();
    cell.restoreVertexCursor = 0U;
    cell.restoreIndexCursor = 0U;
    cell.restoreCopyFrames = 0U;
    cell.restorePrepared = false;

    const std::uint64_t bytes =
        static_cast<std::uint64_t>(
            cell.vertexBytes +
            cell.indexBytes);

    if (bytes <=
        std::numeric_limits<std::uint64_t>::max() -
            geometryResidentBytes_) {
        geometryResidentBytes_ +=
            bytes;
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_RUNTIME_GEOMETRY_GPU_RESTORE_COMPLETE cell=%u copy_frames=%u max_copy_kb=%.1f",
        static_cast<unsigned int>(
            cell.cellId),
        static_cast<unsigned int>(
            copyFrames),
        static_cast<double>(
            copyBudgetBytes) /
            1024.0);

    return GeometryRestoreResult::Complete;
}

std::string VulkanStaticMeshRenderer::geometryRangeRequestKey(
    std::uint32_t cellSlot,
    std::uint32_t batchIndex) const {
    return
        "geometry:" +
        std::to_string(cellSlot) +
        ":" +
        std::to_string(batchIndex);
}

void VulkanStaticMeshRenderer::serviceRuntimeGeometryResidency(
    std::uint32_t frameSlot,
    const StreamCellPlanInput& input) noexcept {
    (void) input;
    if (!streamGraphReady_ ||
        frameSlot >= kDescriptorFrames ||
        geometryCellCount_ == 0U ||
        geometryAssetPath_.empty() ||
        geometryDirectory_.version <
            kStaticMeshNormalsVersion ||
        geometryDirectory_.batches.size() !=
            batches_.size()) {
        return;
    }

    const std::uint8_t slotBit =
        static_cast<std::uint8_t>(
            1U << frameSlot);
    const std::uint8_t fullMask =
        static_cast<std::uint8_t>(
            (1U << kDescriptorFrames) - 1U);

    // Cell heat is updated when the stream plan rebuilds. Stable frames
    // keep that state untouched; only the geometry reload probe temporarily
    // overrides one cell instead of rewriting every geometry cell each frame.
    if (geometryResidencyProbeEnabled_ &&
        !geometryResidencyProbeComplete_ &&
        geometryResidencyProbeCellSlot_ <
            geometryCellCount_ &&
        runtimeTextureTransitionFrame_ >=
            geometryResidencyProbeReloadFrame_) {
        geometryCells_[
            geometryResidencyProbeCellSlot_].
                heat =
                    StreamCellHeat::Preload;
    }

    if (geometryReloadCellSlot_ !=
        UINT32_MAX) {
        if (geometryReloadCellSlot_ >=
            geometryCellCount_) {
            geometryReloadCellSlot_ =
                UINT32_MAX;
            return;
        }

        auto& cell =
            geometryCells_[
                geometryReloadCellSlot_];

        if (!cell.reloadActive) {
            geometryReloadCellSlot_ =
                UINT32_MAX;
            return;
        }

        const auto abortReload =
            [&]() noexcept {
                cell.reloadActive = false;
                cell.reloadFailed = false;
                cell.reloadScanCursor = 0U;
                cell.reloadRanges = {};
                cell.reloadPendingCount = 0U;
                cell.reloadPeakPendingCount = 0U;
                cell.reloadPeakCopyBytesPerFrame = 0U;
                cell.reloadStartFrame = 0U;
                cell.reloadVertexBytes.clear();
                cell.reloadIndexBytes.clear();
                geometryReloadCellSlot_ =
                    UINT32_MAX;
            };

        const auto copyReadyRange =
            [&](GeometryRangeInFlight& range,
                VkDeviceSize& remainingBudget)
                noexcept -> bool {
                if (!range.resultReady ||
                    remainingBudget == 0U) {
                    return true;
                }

                const std::uint32_t batchIndex =
                    range.batchIndex;

                if (batchIndex >= batches_.size()) {
                    return false;
                }

                const auto& batch =
                    batches_[batchIndex];

                if (batch.sourceBatchIndex >=
                        geometryDirectory_.
                            batches.size() ||
                    batch.geometryCellSlot !=
                        geometryReloadCellSlot_) {
                    return false;
                }

                const auto& entry =
                    geometryDirectory_.batches[
                        batch.sourceBatchIndex];

                if (entry.indexDataOffset <
                        entry.vertexDataOffset ||
                    entry.payloadBytes <
                        entry.indexDataOffset -
                            entry.vertexDataOffset ||
                    entry.payloadBytes >
                        std::numeric_limits<
                            std::size_t>::max() ||
                    range.readyBytes.size() !=
                        static_cast<std::size_t>(
                            entry.payloadBytes) ||
                    range.copyCursor >
                        range.readyBytes.size()) {
                    return false;
                }

                const std::uint64_t sourceVertexBytes =
                    entry.indexDataOffset -
                    entry.vertexDataOffset;
                const std::uint64_t indexBytes =
                    entry.payloadBytes -
                    sourceVertexBytes;

                if (batch.vertexOffset < 0 ||
                    sourceVertexBytes !=
                        static_cast<std::uint64_t>(
                            entry.vertexCount) *
                            sizeof(StaticMeshVertex)) {
                    return false;
                }

                const std::uint64_t gpuVertexStride =
                    gpuStaticVertexStride(
                        packedStaticVertexEnabled_);
                const std::uint64_t gpuVertexBytes =
                    static_cast<std::uint64_t>(
                        entry.vertexCount) *
                    gpuVertexStride;

                const std::uint64_t vertexDst =
                    static_cast<std::uint64_t>(
                        batch.vertexOffset) *
                    gpuVertexStride;
                const std::uint64_t indexDst =
                    static_cast<std::uint64_t>(
                        batch.firstIndex) *
                    sizeof(std::uint16_t);

                if (vertexDst >
                        cell.reloadVertexBytes.size() ||
                    gpuVertexBytes >
                        cell.reloadVertexBytes.size() -
                            vertexDst ||
                    indexDst >
                        cell.reloadIndexBytes.size() ||
                    indexBytes >
                        cell.reloadIndexBytes.size() -
                            indexDst) {
                    return false;
                }

                while (
                    remainingBudget > 0U &&
                    range.copyCursor <
                        range.readyBytes.size()) {
                    const std::uint64_t payloadCursor =
                        static_cast<std::uint64_t>(
                            range.copyCursor);

                    if (payloadCursor <
                        sourceVertexBytes) {
                        if (packedStaticVertexEnabled_) {
                            if ((payloadCursor %
                                 sizeof(StaticMeshVertex)) !=
                                0U) {
                                return false;
                            }

                            const std::uint64_t remainingVertices =
                                (sourceVertexBytes -
                                 payloadCursor) /
                                sizeof(StaticMeshVertex);
                            const std::uint64_t budgetVertices =
                                remainingBudget /
                                sizeof(StaticMeshVertex);

                            if (budgetVertices == 0U) {
                                remainingBudget = 0U;
                                continue;
                            }

                            const std::uint32_t verticesToPack =
                                static_cast<std::uint32_t>(
                                    std::min<std::uint64_t>(
                                        remainingVertices,
                                        budgetVertices));
                            const std::size_t sourceBytesToPack =
                                static_cast<std::size_t>(
                                    verticesToPack) *
                                sizeof(StaticMeshVertex);
                            const std::uint64_t destinationVertex =
                                payloadCursor /
                                sizeof(StaticMeshVertex);

                            if (!packGpuVerticesFromBytes(
                                    std::span<const std::byte>(
                                        range.readyBytes.data() +
                                            range.copyCursor,
                                        sourceBytesToPack),
                                    verticesToPack,
                                    cell.reloadVertexBytes.data() +
                                        static_cast<std::size_t>(
                                            vertexDst +
                                            destinationVertex *
                                                gpuVertexStride))) {
                                return false;
                            }

                            range.copyCursor +=
                                sourceBytesToPack;
                            remainingBudget -=
                                static_cast<VkDeviceSize>(
                                    sourceBytesToPack);
                            continue;
                        }

                        const VkDeviceSize available =
                            static_cast<VkDeviceSize>(
                                sourceVertexBytes -
                                payloadCursor);
                        const VkDeviceSize amount =
                            std::min(
                                available,
                                remainingBudget);

                        std::memcpy(
                            cell.reloadVertexBytes.data() +
                                static_cast<std::size_t>(
                                    vertexDst +
                                    payloadCursor),
                            range.readyBytes.data() +
                                range.copyCursor,
                            static_cast<std::size_t>(
                                amount));

                        range.copyCursor +=
                            static_cast<std::size_t>(
                                amount);
                        remainingBudget -= amount;
                        continue;
                    }

                    const std::uint64_t indexCursor =
                        payloadCursor -
                        sourceVertexBytes;

                    if (indexCursor >= indexBytes) {
                        return false;
                    }

                    const VkDeviceSize available =
                        static_cast<VkDeviceSize>(
                            indexBytes -
                            indexCursor);
                    const VkDeviceSize amount =
                        std::min(
                            available,
                            remainingBudget);

                    std::memcpy(
                        cell.reloadIndexBytes.data() +
                            static_cast<std::size_t>(
                                indexDst +
                                indexCursor),
                        range.readyBytes.data() +
                            range.copyCursor,
                        static_cast<std::size_t>(
                            amount));

                    range.copyCursor +=
                        static_cast<std::size_t>(
                            amount);
                    remainingBudget -= amount;
                }

                return true;
            };

        // Completed APK ranges remain in their fixed in-flight slots and are
        // assembled under the same per-frame budget as the Vulkan restore.
        // This prevents four workers/results from turning into four large
        // render-thread memcpy bursts in one frame.
        const VkDeviceSize rangeCopyBudget =
            cell.heat == StreamCellHeat::Hot
            ? kGeometryRestoreHotBudgetBytes
            : kGeometryRestorePreloadBudgetBytes;
        VkDeviceSize remainingRangeCopyBudget =
            rangeCopyBudget;

        for (auto& range :
             cell.reloadRanges) {
            if (!range.active) {
                continue;
            }

            if (cell.reloadFailed) {
                if (range.resultReady) {
                    range = {};

                    if (cell.reloadPendingCount > 0U) {
                        --cell.reloadPendingCount;
                    }

                    continue;
                }

                bool finished = false;
                std::vector<std::byte> discardBytes;

                (void) assetStreamer_.tryTake(
                    range.key,
                    discardBytes,
                    finished);

                if (finished) {
                    range = {};

                    if (cell.reloadPendingCount > 0U) {
                        --cell.reloadPendingCount;
                    }
                }

                continue;
            }

            if (!range.resultReady) {
                bool finished = false;
                std::vector<std::byte> bytes;

                const bool success =
                    assetStreamer_.tryTake(
                        range.key,
                        bytes,
                        finished);

                if (!finished) {
                    continue;
                }

                if (!success) {
                    range = {};

                    if (cell.reloadPendingCount > 0U) {
                        --cell.reloadPendingCount;
                    }

                    cell.reloadFailed = true;
                    continue;
                }

                range.readyBytes =
                    std::move(bytes);
                range.copyCursor = 0U;
                range.resultReady = true;
            }

            if (remainingRangeCopyBudget == 0U) {
                continue;
            }

            if (!copyReadyRange(
                    range,
                    remainingRangeCopyBudget)) {
                range = {};

                if (cell.reloadPendingCount > 0U) {
                    --cell.reloadPendingCount;
                }

                cell.reloadFailed = true;
                continue;
            }

            if (range.copyCursor >=
                range.readyBytes.size()) {
                range = {};

                if (cell.reloadPendingCount > 0U) {
                    --cell.reloadPendingCount;
                }
            }
        }

        const VkDeviceSize copiedThisFrame =
            rangeCopyBudget -
            remainingRangeCopyBudget;

        cell.reloadPeakCopyBytesPerFrame =
            std::max(
                cell.reloadPeakCopyBytesPerFrame,
                copiedThisFrame);

        if (cell.reloadFailed) {
            if (cell.reloadPendingCount == 0U) {
                __android_log_print(
                    ANDROID_LOG_WARN,
                    kTag,
                    "XZIEL_RUNTIME_GEOMETRY_RELOAD_FAILED cell=%u slot=%u",
                    static_cast<unsigned int>(
                        cell.cellId),
                    static_cast<unsigned int>(
                        geometryReloadCellSlot_));

                abortReload();
            }

            return;
        }

        // Geometry cells own contiguous upload-time batch ranges. Reload
        // only walks this cell's range instead of rescanning every batch.
        const std::size_t reloadBatchBegin =
            cell.firstBatch;
        const std::size_t reloadBatchEnd =
            reloadBatchBegin <= batches_.size()
            ? std::min<std::size_t>(
                  batches_.size(),
                  reloadBatchBegin +
                      cell.batchCount)
            : 0U;

        if (reloadBatchBegin ==
                UINT32_MAX ||
            reloadBatchBegin >= reloadBatchEnd) {
            cell.reloadFailed = true;
        }

        // Keep a small bounded window full. Four independent range requests
        // allow two worker threads to overlap APK reads without allowing one
        // cell to monopolize the shared streaming budget.
        while (!cell.reloadFailed &&
               cell.reloadPendingCount <
                   kGeometryReloadWindow &&
               cell.reloadScanCursor <
                   reloadBatchEnd) {
            const std::size_t batchIndex =
                cell.reloadScanCursor;

            const auto& batch =
                batches_[batchIndex];

            if (batch.geometryCellSlot !=
                geometryReloadCellSlot_) {
                cell.reloadFailed = true;
                break;
            }

            if (batch.sourceBatchIndex >=
                geometryDirectory_.batches.size()) {
                cell.reloadFailed = true;
                break;
            }

            GeometryRangeInFlight* freeRange =
                nullptr;

            for (auto& range :
                 cell.reloadRanges) {
                if (!range.active) {
                    freeRange = &range;
                    break;
                }
            }

            if (freeRange == nullptr) {
                break;
            }

            const auto& entry =
                geometryDirectory_.batches[
                    batch.sourceBatchIndex];

            const std::string key =
                geometryRangeRequestKey(
                    geometryReloadCellSlot_,
                    static_cast<std::uint32_t>(
                        batchIndex));

            if (!assetStreamer_.enqueueRange(
                    geometryAssetPath_,
                    entry.vertexDataOffset,
                    entry.payloadBytes,
                    key)) {
                cell.reloadFailed = true;
                break;
            }

            freeRange->batchIndex =
                static_cast<std::uint32_t>(
                    batchIndex);
            freeRange->key = key;
            freeRange->active = true;

            ++cell.reloadPendingCount;

            cell.reloadPeakPendingCount =
                std::max(
                    cell.reloadPeakPendingCount,
                    cell.reloadPendingCount);

            cell.reloadScanCursor =
                batchIndex + 1U;
        }

        if (cell.reloadFailed) {
            if (cell.reloadPendingCount == 0U) {
                abortReload();
            }
            return;
        }

        if (cell.reloadScanCursor <
                reloadBatchEnd ||
            cell.reloadPendingCount != 0U) {
            return;
        }

        const std::uint32_t completedSlot =
            geometryReloadCellSlot_;
        const std::uint32_t completedCell =
            cell.cellId;
        const std::uint64_t bytes =
            static_cast<std::uint64_t>(
                cell.vertexBytes +
                cell.indexBytes);
        const std::uint64_t elapsedFrames =
            runtimeTextureTransitionFrame_ >=
                    cell.reloadStartFrame
            ? runtimeTextureTransitionFrame_ -
                  cell.reloadStartFrame
            : 0U;
        const std::uint32_t peakPending =
            cell.reloadPeakPendingCount;
        const VkDeviceSize peakRangeCopyBytes =
            cell.reloadPeakCopyBytesPerFrame;

        const VkDeviceSize restoreCopyBudget =
            cell.heat == StreamCellHeat::Hot
            ? kGeometryRestoreHotBudgetBytes
            : kGeometryRestorePreloadBudgetBytes;

        const GeometryRestoreResult restoreResult =
            restoreGeometryCellGpuResidency(
                cell,
                restoreCopyBudget);

        if (restoreResult ==
            GeometryRestoreResult::Failed) {
            abortReload();
            return;
        }

        if (restoreResult ==
            GeometryRestoreResult::InProgress) {
            return;
        }

        geometryReloadCellSlot_ =
            UINT32_MAX;

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_RUNTIME_GEOMETRY_RELOAD_COMPLETE cell=%u slot=%u resident_mb=%.2f total_resident_mb=%.2f peak_pending=%u peak_range_copy_kb=%.1f elapsed_frames=%llu",
            static_cast<unsigned int>(
                completedCell),
            static_cast<unsigned int>(
                completedSlot),
            static_cast<double>(
                bytes) /
                (1024.0 * 1024.0),
            static_cast<double>(
                geometryResidentBytes_) /
                (1024.0 * 1024.0),
            static_cast<unsigned int>(
                peakPending),
            static_cast<double>(
                peakRangeCopyBytes) /
                1024.0,
            static_cast<unsigned long long>(
                elapsedFrames));

        if (geometryResidencyProbeEnabled_ &&
            geometryResidencyProbeCellSlot_ ==
                completedSlot) {
            geometryResidencyProbeComplete_ =
                true;
            cell.heat =
                cell.pinned
                ? StreamCellHeat::Hot
                : cell.plannedHeat;
        }

        return;
    }

    const std::uint64_t effectiveGeometryBudget =
        effectiveGeometryResidentBudget(
            geometryResidentBudgetBytes_,
            input.memoryPressure);

    const bool geometryOverBudget =
        geometryResidentBytes_ >
        effectiveGeometryBudget;

    // A missing Hot/Preload cell is player-visible, so reload it before
    // spending a frame retiring unrelated Cold cells.
    for (StreamCellHeat targetHeat :
         {StreamCellHeat::Hot,
          StreamCellHeat::Preload}) {
        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            auto& cell =
                geometryCells_[i];

            if (cell.pinned ||
                cell.physicallyResident ||
                cell.reloadActive ||
                cell.heat != targetHeat) {
                continue;
            }

            if (cell.vertexBytes >
                    std::numeric_limits<
                        std::size_t>::max() ||
                cell.indexBytes >
                    std::numeric_limits<
                        std::size_t>::max()) {
                continue;
            }

            const std::uint64_t cellBytes =
                static_cast<std::uint64_t>(
                    cell.vertexBytes +
                    cell.indexBytes);

            if (targetHeat ==
                    StreamCellHeat::Preload &&
                cellBytes >
                    effectiveGeometryBudget -
                        std::min(
                            effectiveGeometryBudget,
                            geometryResidentBytes_)) {
                if (!cell.budgetBlockedLogged) {
                    cell.budgetBlockedLogged = true;

                    __android_log_print(
                        ANDROID_LOG_INFO,
                        kTag,
                        "XZIEL_GEOMETRY_PRELOAD_BUDGET_BLOCKED cell=%u bytes_mb=%.2f resident_mb=%.2f budget_mb=%.2f pressure=%u",
                        static_cast<unsigned int>(
                            cell.cellId),
                        static_cast<double>(
                            cellBytes) /
                            (1024.0 * 1024.0),
                        static_cast<double>(
                            geometryResidentBytes_) /
                            (1024.0 * 1024.0),
                        static_cast<double>(
                            effectiveGeometryBudget) /
                            (1024.0 * 1024.0),
                        static_cast<unsigned int>(
                            input.memoryPressure));
                }

                continue;
            }

            cell.budgetBlockedLogged = false;

            try {
                cell.reloadVertexBytes.assign(
                    static_cast<std::size_t>(
                        cell.vertexBytes),
                    std::byte{0});
                cell.reloadIndexBytes.assign(
                    static_cast<std::size_t>(
                        cell.indexBytes),
                    std::byte{0});
            } catch (...) {
                cell.reloadVertexBytes.clear();
                cell.reloadIndexBytes.clear();
                continue;
            }

            cell.reloadActive = true;
            cell.reloadFailed = false;
            cell.reloadScanCursor =
                cell.firstBatch;
            cell.reloadRanges = {};
            cell.reloadPendingCount = 0U;
            cell.reloadPeakPendingCount = 0U;
            cell.reloadPeakCopyBytesPerFrame = 0U;
            cell.reloadStartFrame =
                runtimeTextureTransitionFrame_;
            geometryReloadCellSlot_ =
                static_cast<std::uint32_t>(
                    i);

            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_RUNTIME_GEOMETRY_CELL_RANGE_RELOAD_ACTIVE cell=%u first_batch=%u batch_count=%u",
                static_cast<unsigned int>(
                    cell.cellId),
                static_cast<unsigned int>(
                    cell.firstBatch),
                static_cast<unsigned int>(
                    cell.batchCount));

            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_RUNTIME_GEOMETRY_RELOAD_QUEUED cell=%u slot=%u bytes_mb=%.2f heat=%u",
                static_cast<unsigned int>(
                    cell.cellId),
                static_cast<unsigned int>(i),
                static_cast<double>(
                    static_cast<std::uint64_t>(
                        cell.vertexBytes +
                        cell.indexBytes)) /
                    (1024.0 * 1024.0),
                static_cast<unsigned int>(
                    cell.heat));

            return;
        }
    }

    const bool preserveResidentGeometry =
        !geometryResidencyProbeEnabled_ &&
        !geometryOverBudget &&
        input.memoryPressure ==
            MemoryPressure::Normal;

    if (preserveResidentGeometry) {
        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            geometryCells_[i].retireMask = 0U;
        }

        return;
    }

    const std::uint32_t minimumStableFrames =
        geometryResidencyProbeEnabled_ ||
                geometryOverBudget
        ? 8U
        : input.memoryPressure ==
              MemoryPressure::Critical
          ? 8U
          : input.memoryPressure ==
                MemoryPressure::Elevated
            ? 30U
            : 120U;

    for (std::size_t i = 0U;
         i < geometryCellCount_;
         ++i) {
        auto& cell =
            geometryCells_[i];

        if (cell.pinned ||
            !cell.physicallyResident) {
            continue;
        }

        if (cell.heat !=
                StreamCellHeat::Cold ||
            !streamCullingActive_ ||
            streamCellStableFrames_ <
                minimumStableFrames) {
            cell.retireMask = 0U;
            continue;
        }

        cell.retireMask |=
            slotBit;

        if (cell.retireMask !=
            fullMask) {
            return;
        }

        const std::uint64_t freedBytes =
            static_cast<std::uint64_t>(
                cell.vertexBytes +
                cell.indexBytes);
        const std::uint32_t evictedCell =
            cell.cellId;

        releaseGeometryCellGpuResidency(
            cell);

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_RUNTIME_GEOMETRY_EVICTED cell=%u slot=%u freed_mb=%.2f total_resident_mb=%.2f pressure=%u budget_mb=%.2f over_budget=%u",
            static_cast<unsigned int>(
                evictedCell),
            static_cast<unsigned int>(i),
            static_cast<double>(
                freedBytes) /
                (1024.0 * 1024.0),
            static_cast<double>(
                geometryResidentBytes_) /
                (1024.0 * 1024.0),
            static_cast<unsigned int>(
                input.memoryPressure),
            static_cast<double>(
                effectiveGeometryBudget) /
                (1024.0 * 1024.0),
            geometryOverBudget ? 1U : 0U);

        if (geometryResidencyProbeEnabled_ &&
            !geometryResidencyProbeComplete_ &&
            geometryResidencyProbeCellSlot_ ==
                UINT32_MAX) {
            geometryResidencyProbeCellSlot_ =
                static_cast<std::uint32_t>(
                    i);
            geometryResidencyProbeReloadFrame_ =
                runtimeTextureTransitionFrame_ +
                12U;

            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_RUNTIME_GEOMETRY_RELOAD_PROBE_ARMED cell=%u slot=%u reload_frame=%llu",
                static_cast<unsigned int>(
                    evictedCell),
                static_cast<unsigned int>(i),
                static_cast<unsigned long long>(
                    geometryResidencyProbeReloadFrame_));
        }

        return;
    }
}

void VulkanStaticMeshRenderer::record(
    VkCommandBuffer command,
    VkExtent2D extent,
    std::uint32_t frameSlot,
    const StaticMeshCameraState& camera,
    const StaticMeshEnvironmentState& environment) noexcept {
    frameStats_ = {};

    if (!ready_ ||
        command == VK_NULL_HANDLE ||
        extent.width == 0U ||
        extent.height == 0U) {
        return;
    }

    // Capacity is reserved once during initialization. clear() keeps the hot
    // render path allocation-free while rebuilding only the current frame's
    // visible draw list.
    visibleDrawCandidates_.clear();
    drawCommands_.clear();
    drawGroups_.clear();

    if (streamGraphReady_) {
        const std::uint32_t currentCell =
            inferStreamingCell(camera);

        if (currentCell != 0U) {
            if (currentCell !=
                streamCellCandidate_) {
                streamCellCandidate_ =
                    currentCell;
                streamCellStableFrames_ =
                    1U;
                streamCullingActive_ =
                    false;
                streamCullLogged_ =
                    false;
            } else {
                streamCellStableFrames_ =
                    std::min<std::uint32_t>(
                        streamCellStableFrames_ + 1U,
                        1000000U);

                if (streamCellStableFrames_ >= 8U) {
                    streamCullingActive_ =
                        true;
                }
            }

            const StreamCellPlanInput planInput{
                .currentCell = currentCell,
                .preloadPortalHops = 1U,
                .memoryPressure =
                    environment.memoryPressure,
            };

            const bool planRebuilt =
                streamPlanDirty_ ||
                cachedStreamPlanCell_ !=
                    currentCell ||
                cachedStreamPlanPressure_ !=
                    environment.memoryPressure;

            if (planRebuilt) {
                std::array<
                    StreamCellPlanCellState,
                    kMaxStreamCells> plannedCells{};
                std::size_t plannedCellCount = 0U;

                cachedStreamPlanStats_ =
                    streamGraph_.plan(
                        planInput,
                        streamDecisions_.data(),
                        streamDecisions_.size(),
                        streamDecisionCount_,
                        plannedCells.data(),
                        plannedCells.size(),
                        &plannedCellCount);

                cachedStreamPlanCell_ =
                    currentCell;
                cachedStreamPlanPressure_ =
                    environment.memoryPressure;
                cachedStreamColdBatches_ = 0U;
                streamPlanDirty_ = false;
                ++streamPlanBuildCount_;

                geometryPortalReachable_.fill(0U);

                for (std::size_t i = 0U;
                     i < geometryCellCount_;
                     ++i) {
                    auto& cell =
                        geometryCells_[i];

                    cell.plannedHeat =
                        cell.pinned
                        ? StreamCellHeat::Hot
                        : StreamCellHeat::Cold;

                    bool portalReachable =
                        cell.pinned ||
                        cell.cellId == 0U;

                    if (!cell.pinned &&
                        cell.cellId != 0U) {
                        const StreamCellPlanCellState*
                            state = nullptr;

                        if (cell.streamPlanCellSlot <
                                plannedCellCount &&
                            plannedCells[
                                cell.streamPlanCellSlot].
                                    cellId ==
                                cell.cellId) {
                            state =
                                &plannedCells[
                                    cell.streamPlanCellSlot];
                        } else {
                            for (std::size_t stateIndex = 0U;
                                 stateIndex <
                                     plannedCellCount;
                                 ++stateIndex) {
                                if (plannedCells[
                                        stateIndex].
                                            cellId ==
                                    cell.cellId) {
                                    state =
                                        &plannedCells[
                                            stateIndex];
                                    break;
                                }
                            }
                        }

                        if (state != nullptr) {
                            cell.plannedHeat =
                                state->heat;
                            portalReachable =
                                state->
                                    reachableThroughOpenPortals;
                        }
                    }

                    cell.heat =
                        cell.plannedHeat;

                    geometryPortalReachable_[i] =
                        portalReachable
                        ? static_cast<std::uint8_t>(1U)
                        : static_cast<std::uint8_t>(0U);

                    ++streamCellHeatRefreshCount_;
                }

                std::uint32_t directPlanCellReads = 0U;
                std::uint32_t fallbackPlanCellScans = 0U;

                for (std::size_t i = 0U;
                     i < geometryCellCount_;
                     ++i) {
                    const auto& cell =
                        geometryCells_[i];

                    if (cell.pinned ||
                        cell.cellId == 0U) {
                        continue;
                    }

                    if (cell.streamPlanCellSlot <
                            plannedCellCount &&
                        plannedCells[
                            cell.streamPlanCellSlot].
                                cellId ==
                            cell.cellId) {
                        ++directPlanCellReads;
                    } else {
                        ++fallbackPlanCellScans;
                    }
                }

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_STREAM_PLAN_CELL_INDEX_ACTIVE direct=%u fallback=%u geometry_cells=%u",
                    static_cast<unsigned int>(
                        directPlanCellReads),
                    static_cast<unsigned int>(
                        fallbackPlanCellScans),
                    static_cast<unsigned int>(
                        geometryCellCount_));

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_STREAM_GRAPH_SINGLE_TRAVERSAL_ACTIVE cells=%u geometry_cells=%u",
                    static_cast<unsigned int>(
                        plannedCellCount),
                    static_cast<unsigned int>(
                        geometryCellCount_));

                cachedPortalReachabilityCell_ =
                    currentCell;
                portalReachabilityCacheValid_ = true;

                std::uint32_t indexedTextureDecisions = 0U;

                for (auto& texture : textures_) {
                    texture.streamDecisionSlot =
                        UINT32_MAX;

                    const auto* decision =
                        streamDecision(
                            texture.streamResourceId,
                            streamDecisionCount_);

                    if (decision != nullptr) {
                        texture.streamDecisionSlot =
                            static_cast<std::uint32_t>(
                                decision -
                                streamDecisions_.data());
                        ++indexedTextureDecisions;
                    }
                }

                std::uint32_t indexedMaterialDecisions = 0U;

                for (auto& material : materials_) {
                    material.streamDecisionSlot =
                        UINT32_MAX;

                    if (material.albedoTextureIndex <
                        textures_.size()) {
                        const auto& albedo =
                            textures_[
                                material.
                                    albedoTextureIndex];

                        if (albedo.streamResourceId ==
                            material.streamResourceId) {
                            material.streamDecisionSlot =
                                albedo.
                                    streamDecisionSlot;
                        }
                    }

                    if (material.streamDecisionSlot ==
                        UINT32_MAX) {
                        const auto* decision =
                            streamDecision(
                                material.streamResourceId,
                                streamDecisionCount_);

                        if (decision != nullptr) {
                            material.streamDecisionSlot =
                                static_cast<std::uint32_t>(
                                    decision -
                                    streamDecisions_.data());
                        }
                    }

                    if (material.streamDecisionSlot !=
                        UINT32_MAX) {
                        ++indexedMaterialDecisions;
                    }
                }

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_STREAM_DECISION_INDEX_READY textures=%u materials=%u decisions=%u",
                    static_cast<unsigned int>(
                        indexedTextureDecisions),
                    static_cast<unsigned int>(
                        indexedMaterialDecisions),
                    static_cast<unsigned int>(
                        streamDecisionCount_));

                for (const auto& batch :
                     batches_) {
                    const StreamCellResourceDecision*
                        decision = nullptr;

                    if (batch.materialIndex <
                        materials_.size()) {
                        const auto& material =
                            materials_[
                                batch.materialIndex];

                        decision =
                            streamDecisionAt(
                                material.streamDecisionSlot,
                                material.streamResourceId,
                                streamDecisionCount_);
                    } else {
                        decision =
                            streamDecision(
                                batch.streamResourceId,
                                streamDecisionCount_);
                    }

                    if (decision != nullptr &&
                        !decision->desiredResident) {
                        ++cachedStreamColdBatches_;
                    }
                }
            } else {
                ++streamPlanCacheHitCount_;
            }

            const auto& streamStats =
                cachedStreamPlanStats_;

            frameStats_.streamingCell =
                currentCell;
            frameStats_.streamingHotResources =
                streamStats.hotResources;
            frameStats_.
                streamingPreloadResources =
                streamStats.preloadResources;
            frameStats_.
                streamingEvictableBytes =
                streamStats.evictableBytes;
            frameStats_.streamingColdBatches =
                cachedStreamColdBatches_;

            ++streamPlanFrame_;

            if (currentCell !=
                    lastLoggedStreamCell_ ||
                planRebuilt ||
                (streamPlanFrame_ % 240U) ==
                    0U) {
                lastLoggedStreamCell_ =
                    currentCell;

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_WORLD_STREAMING_PLAN current_cell=%u hot_resources=%u preload_resources=%u cold_resources=%u cold_batches=%u desired_mb=%.2f evictable_mb=%.2f pressure=%u plan_rebuilt=%u plan_builds=%llu plan_cache_hits=%llu",
                    static_cast<unsigned int>(
                        currentCell),
                    static_cast<unsigned int>(
                        streamStats.hotResources),
                    static_cast<unsigned int>(
                        streamStats.preloadResources),
                    static_cast<unsigned int>(
                        streamStats.coldResources),
                    static_cast<unsigned int>(
                        frameStats_.
                            streamingColdBatches),
                    static_cast<double>(
                        streamStats.
                            desiredResidentBytes) /
                        (1024.0 * 1024.0),
                    static_cast<double>(
                        streamStats.
                            evictableBytes) /
                        (1024.0 * 1024.0),
                    static_cast<unsigned int>(
                        environment.
                            memoryPressure),
                    planRebuilt ? 1U : 0U,
                    static_cast<unsigned long long>(
                        streamPlanBuildCount_),
                    static_cast<unsigned long long>(
                        streamPlanCacheHitCount_));
            }
        } else {
            streamCellCandidate_ = 0U;
            streamCellStableFrames_ = 0U;
            streamCullingActive_ = false;
            streamCullLogged_ = false;
            streamDecisionCount_ = 0U;
            cachedStreamPlanStats_ = {};
            cachedStreamPlanCell_ = 0U;
            cachedStreamColdBatches_ = 0U;
            cachedPortalReachabilityCell_ = 0U;
            portalReachabilityCacheValid_ = false;
            geometryPortalReachable_.fill(0U);
            streamPlanDirty_ = true;
        }
    }

    serviceRuntimeTextureResidency(
        frameSlot,
        environment.memoryPressure);

    if (streamGraphReady_ &&
        frameStats_.streamingCell != 0U) {
        serviceRuntimeGeometryResidency(
            frameSlot,
            {
                .currentCell =
                    frameStats_.streamingCell,
                .preloadPortalHops = 1U,
                .memoryPressure =
                    environment.memoryPressure,
            });
    }

    VkPipeline boundPipeline =
        VK_NULL_HANDLE;
    std::uint32_t boundMaterialIndex =
        UINT32_MAX;

    VkViewport viewport{};
    viewport.x = 0.0f;
    viewport.y = 0.0f;
    viewport.width =
        static_cast<float>(extent.width);
    viewport.height =
        static_cast<float>(extent.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;

    VkRect2D scissor{};
    scissor.extent = extent;

    vkCmdSetViewport(
        command,
        0U,
        1U,
        &viewport);

    vkCmdSetScissor(
        command,
        0U,
        1U,
        &scissor);

    PushConstants push{};
    push.cameraX = camera.x;
    push.cameraY = camera.y;
    push.cameraZ = camera.z;
    push.viewYawCos =
        std::cos(camera.yawRadians);
    push.viewYawSin =
        std::sin(camera.yawRadians);
    push.viewPitchCos =
        std::cos(camera.pitchRadians);
    push.viewPitchSin =
        std::sin(camera.pitchRadians);

    constexpr float kDegreesToRadians =
        0.01745329251994329577f;
    const float clampedFovDegrees =
        std::clamp(
            camera.verticalFovDegrees,
            50.0f,
            110.0f);
    const float safeAspect =
        std::max(camera.aspect, 0.25f);

    if (cachedWorldProjectionFovDegrees_ ==
            clampedFovDegrees &&
        cachedWorldProjectionAspect_ ==
            safeAspect) {
        ++worldProjectionCacheHits_;
    } else {
        const float projectionFocal =
            1.0f /
            std::tan(
                clampedFovDegrees *
                0.5f *
                kDegreesToRadians);

        cachedWorldProjectionFovDegrees_ =
            clampedFovDegrees;
        cachedWorldProjectionAspect_ =
            safeAspect;
        cachedWorldProjectionFocal_ =
            projectionFocal;
        cachedWorldProjectionFocalOverAspect_ =
            projectionFocal / safeAspect;
    }

    push.projectionFocal =
        cachedWorldProjectionFocal_;
    push.projectionFocalOverAspect =
        cachedWorldProjectionFocalOverAspect_;
    push.fogDensity =
        std::clamp(
            environment.fogDensity,
            0.0f,
            1.0f);
    push.lightningFlash =
        1.0f +
        std::clamp(
            environment.lightningFlash,
            0.0f,
            2.0f) *
            1.8f;
    push.modelScale = 1.0f;
    push.viewmodelMode = 0U;

    const auto applyMaterial =
        [&](const GpuMaterial& material) noexcept {
            PushConstants materialPush = push;

            materialPush.baseColorFactorR =
                material.baseColorFactor[0];
            materialPush.baseColorFactorG =
                material.baseColorFactor[1];
            materialPush.baseColorFactorB =
                material.baseColorFactor[2];
            materialPush.baseColorFactorA =
                material.baseColorFactor[3];
            materialPush.metallicFactor =
                material.pushMetallicFactor;
            materialPush.roughnessFactor =
                material.pushRoughnessFactor;
            materialPush.normalScale =
                material.pushNormalScale;
            materialPush.occlusionStrength =
                material.pushOcclusionStrength;
            materialPush.emissiveFactorR =
                material.emissiveFactor[0];
            materialPush.emissiveFactorG =
                material.emissiveFactor[1];
            materialPush.emissiveFactorB =
                material.emissiveFactor[2];

            materialPush.materialFlags =
                material.pushMaterialFlags;

            vkCmdPushConstants(
                command,
                pipelineLayout_,
                VK_SHADER_STAGE_VERTEX_BIT |
                    VK_SHADER_STAGE_FRAGMENT_BIT,
                0U,
                static_cast<std::uint32_t>(
                    sizeof(materialPush)),
                &materialPush);
        };

    const bool cellGeometry =
        streamGraphReady_;

    if (cellGeometry) {
        if (geometryCellCount_ == 0U) {
            return;
        }
    } else {
        if (geometryVertexBuffer_ == VK_NULL_HANDLE ||
            geometryIndexBuffer_ == VK_NULL_HANDLE) {
            return;
        }

        const VkDeviceSize geometryOffset = 0U;

        vkCmdBindVertexBuffers(
            command,
            0U,
            1U,
            &geometryVertexBuffer_,
            &geometryOffset);

        vkCmdBindIndexBuffer(
            command,
            geometryIndexBuffer_,
            0U,
            VK_INDEX_TYPE_UINT16);
    }

    std::uint32_t boundGeometryCell =
        UINT32_MAX;

    // Reuse the camera terms already evaluated for push constants.
    // This culling path runs every frame, so avoid duplicate trig work.
    const float yawCos =
        push.viewYawCos;
    const float yawSin =
        push.viewYawSin;
    const float pitchCos =
        push.viewPitchCos;
    const float pitchSin =
        push.viewPitchSin;
    const float tanHalfFov =
        1.0f /
        cachedWorldProjectionFocal_;
    constexpr float nearPlane = 0.08f;
    constexpr float farPlane = 180.0f;

    const auto sphereVisible =
        [&](float centerX,
            float centerY,
            float centerZ,
            float radius,
            float* visibleNearDepth) noexcept {
            const float relativeX =
                centerX - camera.x;
            const float relativeY =
                centerY - camera.y;
            const float relativeZ =
                centerZ - camera.z;

            const float yawViewX =
                yawCos * relativeX -
                yawSin * relativeZ;
            const float yawViewZ =
                yawSin * relativeX +
                yawCos * relativeZ;

            const float viewY =
                pitchCos * relativeY +
                pitchSin * yawViewZ;
            const float viewZ =
                -pitchSin * relativeY +
                pitchCos * yawViewZ;

            if (viewZ + radius < nearPlane ||
                viewZ - radius > farPlane) {
                return false;
            }

            const float projectedDepth =
                std::max(
                    viewZ,
                    nearPlane);
            const float halfHeight =
                projectedDepth *
                tanHalfFov;
            const float halfWidth =
                halfHeight *
                safeAspect;

            const bool visible =
                std::abs(yawViewX) - radius <=
                    halfWidth &&
                std::abs(viewY) - radius <=
                    halfHeight;

            if (visible &&
                visibleNearDepth != nullptr) {
                *visibleNearDepth =
                    std::max(
                        nearPlane,
                        viewZ -
                            std::max(
                                radius,
                                0.0f));
            }

            return visible;
        };

    const bool materialVisibilityCacheReady =
        materialVisibilityStates_.size() ==
            materials_.size() &&
        materialVisibilityGenerations_.size() ==
            materials_.size();

    if (materialVisibilityCacheReady) {
        ++materialVisibilityGeneration_;

        // Generation zero is reserved for never-written entries. This path
        // runs only after ~4.29 billion frames, so the linear clear is
        // effectively absent from normal gameplay.
        if (materialVisibilityGeneration_ == 0U) {
            std::fill(
                materialVisibilityGenerations_.begin(),
                materialVisibilityGenerations_.end(),
                0U);
            materialVisibilityGeneration_ = 1U;
        }
    }

    const auto visitBatch =
        [&](std::size_t batchIndex) noexcept {
            if (batchIndex >= batches_.size()) {
                return;
            }

            const auto& batch =
                batches_[batchIndex];

            if (cellGeometry) {
                ++frameStats_.
                    cellDrivenBatchVisits;
            }

            if (batch.materialIndex >=
                materials_.size()) {
                return;
            }

            bool materialVisible = true;

            if (materialVisibilityCacheReady) {
                auto& cachedState =
                    materialVisibilityStates_[
                        batch.materialIndex];
                auto& cachedGeneration =
                    materialVisibilityGenerations_[
                        batch.materialIndex];

                if (cachedGeneration !=
                    materialVisibilityGeneration_) {
                    ++frameStats_.
                        materialVisibilityTests;

                    materialVisible =
                        materialStreamingReady(
                            materials_[
                                batch.materialIndex],
                            frameSlot);

                    if (materialVisible &&
                        streamCullingActive_) {
                        const auto& material =
                            materials_[
                                batch.materialIndex];
                        const auto* decision =
                            streamDecisionAt(
                                material.streamDecisionSlot,
                                material.streamResourceId,
                                streamDecisionCount_);

                        materialVisible =
                            decision == nullptr ||
                            decision->desiredResident;
                    }

                    cachedState =
                        materialVisible
                        ? static_cast<std::uint8_t>(1U)
                        : static_cast<std::uint8_t>(2U);
                    cachedGeneration =
                        materialVisibilityGeneration_;
                } else {
                    ++frameStats_.
                        materialVisibilityCacheHits;
                    materialVisible =
                        cachedState ==
                        static_cast<std::uint8_t>(1U);
                }
            } else {
                ++frameStats_.
                    materialVisibilityTests;

                materialVisible =
                    materialStreamingReady(
                        materials_[
                            batch.materialIndex],
                        frameSlot);

                if (materialVisible &&
                    streamCullingActive_) {
                    const auto& material =
                        materials_[
                            batch.materialIndex];
                    const auto* decision =
                        streamDecisionAt(
                            material.streamDecisionSlot,
                            material.streamResourceId,
                            streamDecisionCount_);

                    materialVisible =
                        decision == nullptr ||
                        decision->desiredResident;
                }
            }

            if (!materialVisible) {
                ++frameStats_.culledBatches;
                ++frameStats_.
                    streamingCulledBatches;
                return;
            }

            ++frameStats_.batchFrustumTests;

            float visibleNearDepth = nearPlane;

            if (!sphereVisible(
                    batch.cullCenterX,
                    batch.cullCenterY,
                    batch.cullCenterZ,
                    batch.cullRadius,
                    &visibleNearDepth)) {
                ++frameStats_.culledBatches;
                return;
            }

            const VkPipeline desiredPipeline =
                batch.doubleSided
                ? pipelineDoubleSided_
                : pipeline_;

            if (desiredPipeline == VK_NULL_HANDLE) {
                ++frameStats_.culledBatches;
                return;
            }

            ++frameStats_.visibleBatches;

            VisibleDrawCandidate candidate{};
            candidate.batchIndex =
                static_cast<std::uint32_t>(
                    batchIndex);
            candidate.originalOrder =
                static_cast<std::uint32_t>(
                    visibleDrawCandidates_.size());
            candidate.viewDepth =
                visibleNearDepth;
            ++frameStats_.
                frontToBackDepthReuses;

            visibleDrawCandidates_.push_back(
                candidate);
        };

    if (cellGeometry) {
        // Geometry was permanently sorted by cell at upload time and every
        // cell owns one contiguous [firstBatch, firstBatch + batchCount)
        // range. Drive traversal from those ranges so cold/occluded cells
        // never enter the per-batch hot loop at all.
        for (std::size_t cellSlot = 0U;
             cellSlot < geometryCellCount_;
             ++cellSlot) {
            const auto& geometryCell =
                geometryCells_[cellSlot];

            if (geometryCell.firstBatch ==
                    UINT32_MAX ||
                geometryCell.batchCount == 0U) {
                continue;
            }

            const std::size_t cellBegin =
                static_cast<std::size_t>(
                    geometryCell.firstBatch);
            const std::size_t cellEnd =
                std::min<std::size_t>(
                    batches_.size(),
                    cellBegin +
                        static_cast<std::size_t>(
                            geometryCell.batchCount));

            if (cellBegin >= cellEnd) {
                continue;
            }

            const std::uint32_t cellBatchCount =
                static_cast<std::uint32_t>(
                    cellEnd - cellBegin);

            const bool streamCold =
                streamCullingActive_ &&
                geometryCell.heat ==
                    StreamCellHeat::Cold;

            const bool missingGeometry =
                !geometryCell.physicallyResident ||
                geometryCell.vertexBuffer ==
                    VK_NULL_HANDLE ||
                geometryCell.indexBuffer ==
                    VK_NULL_HANDLE;

            if (missingGeometry ||
                streamCold) {
                frameStats_.culledBatches +=
                    cellBatchCount;
                frameStats_.
                    streamingCulledBatches +=
                    cellBatchCount;
                frameStats_.
                    cellRangeSkippedBatches +=
                    cellBatchCount;
                continue;
            }

            if (streamCullingActive_ &&
                frameStats_.streamingCell != 0U &&
                geometryCell.cellId != 0U) {
                ++frameStats_.portalVisibilityTests;

                const bool portalReachable =
                    portalReachabilityCacheValid_ &&
                    cachedPortalReachabilityCell_ ==
                        frameStats_.streamingCell &&
                    cellSlot <
                        geometryPortalReachable_.size()
                    ? geometryPortalReachable_[
                          cellSlot] != 0U
                    : streamGraph_.
                          cellReachableThroughOpenPortals(
                              frameStats_.streamingCell,
                              geometryCell.cellId);

                if (!portalReachable) {
                    ++frameStats_.portalVisibilityCulled;
                    frameStats_.culledBatches +=
                        cellBatchCount;
                    frameStats_.
                        cellRangeSkippedBatches +=
                        cellBatchCount;
                    frameStats_.portalSkippedBatches +=
                        cellBatchCount;
                    continue;
                }
            }

            const StreamCellBounds* cellBounds =
                nullptr;

            if (geometryCell.streamBoundsSlot <
                streamCellBounds_.size()) {
                const auto& indexedBounds =
                    streamCellBounds_[
                        geometryCell.
                            streamBoundsSlot];

                if (indexedBounds.valid) {
                    cellBounds =
                        &indexedBounds;
                }
            }

            if (cellBounds != nullptr) {
                ++frameStats_.
                    cellFrustumTests;

                if (!sphereVisible(
                        cellBounds->cullCenterX,
                        cellBounds->cullCenterY,
                        cellBounds->cullCenterZ,
                        cellBounds->cullRadius,
                        nullptr)) {
                    ++frameStats_.
                        cellFrustumCulled;
                    frameStats_.
                        culledBatches +=
                        cellBatchCount;
                    frameStats_.
                        cellRangeSkippedBatches +=
                        cellBatchCount;
                    frameStats_.
                        cellFrustumSkippedBatches +=
                        cellBatchCount;
                    continue;
                }
            }

            for (std::size_t batchIndex =
                     cellBegin;
                 batchIndex < cellEnd;
                 ++batchIndex) {
                visitBatch(batchIndex);
            }
        }
    } else {
        for (std::size_t batchIndex = 0U;
             batchIndex < batches_.size();
             ++batchIndex) {
            visitBatch(batchIndex);
        }
    }

    frameStats_.frontToBackCandidates =
        static_cast<std::uint32_t>(
            visibleDrawCandidates_.size());

    if (visibleDrawCandidates_.size() > 1U) {
        const auto depthLess =
            [&](const VisibleDrawCandidate& a,
                const VisibleDrawCandidate& b) noexcept {
                if (a.viewDepth !=
                    b.viewDepth) {
                    return
                        a.viewDepth <
                        b.viewDepth;
                }

                return
                    batches_[a.batchIndex].
                        sourceBatchIndex <
                    batches_[b.batchIndex].
                        sourceBatchIndex;
            };

        if (cellGeometry) {
            // Cell geometry is permanently sorted at upload time by
            // geometry/material/cull mode. Visibility only removes entries,
            // so compatible submission groups remain contiguous here.
            // Sorting depth inside each group preserves the exact grouping
            // needed by multi-draw-indirect without paying for a global
            // O(N log N) key comparison every frame.
            std::size_t groupBegin = 0U;

            while (groupBegin <
                   visibleDrawCandidates_.size()) {
                const auto& firstBatch =
                    batches_[
                        visibleDrawCandidates_[
                            groupBegin].
                            batchIndex];
                const std::uint32_t groupId =
                    firstBatch.submissionGroupId;

                std::size_t groupEnd =
                    groupBegin + 1U;

                while (groupEnd <
                       visibleDrawCandidates_.size()) {
                    const auto& candidateBatch =
                        batches_[
                            visibleDrawCandidates_[
                                groupEnd].
                                batchIndex];

                    if (candidateBatch.
                            submissionGroupId !=
                        groupId) {
                        break;
                    }

                    ++groupEnd;
                }

                if (groupEnd -
                        groupBegin >
                    1U) {
                    std::sort(
                        visibleDrawCandidates_.
                            begin() +
                            static_cast<
                                std::ptrdiff_t>(
                                groupBegin),
                        visibleDrawCandidates_.
                            begin() +
                            static_cast<
                                std::ptrdiff_t>(
                                groupEnd),
                        depthLess);
                }

                groupBegin = groupEnd;
            }
        } else {
            // Legacy/shared geometry is not guaranteed to be pre-grouped.
            // Keep the full ordering comparator for that compatibility path.
            std::sort(
                visibleDrawCandidates_.begin(),
                visibleDrawCandidates_.end(),
                [&](const VisibleDrawCandidate& a,
                    const VisibleDrawCandidate& b) noexcept {
                    const auto& batchA =
                        batches_[a.batchIndex];
                    const auto& batchB =
                        batches_[b.batchIndex];

                    if (batchA.geometryCellSlot !=
                        batchB.geometryCellSlot) {
                        return
                            batchA.geometryCellSlot <
                            batchB.geometryCellSlot;
                    }

                    if (batchA.materialIndex !=
                        batchB.materialIndex) {
                        return
                            batchA.materialIndex <
                            batchB.materialIndex;
                    }

                    if (batchA.doubleSided !=
                        batchB.doubleSided) {
                        return
                            batchA.doubleSided <
                            batchB.doubleSided;
                    }

                    return depthLess(a, b);
                });
        }

        for (std::uint32_t i = 0U;
             i <
                 static_cast<std::uint32_t>(
                     visibleDrawCandidates_.size());
             ++i) {
            if (visibleDrawCandidates_[i].
                    originalOrder != i) {
                ++frameStats_.
                    frontToBackReordered;
            }
        }
    }

    const std::uint32_t indirectFrameSlot =
        frameSlot % kDescriptorFrames;
    auto& indirectFrame =
        indirectDrawFrames_[
            indirectFrameSlot];

    const VkDeviceSize visibleCommandBytes =
        static_cast<VkDeviceSize>(
            visibleDrawCandidates_.size()) *
        sizeof(VkDrawIndexedIndirectCommand);

    const bool useIndirect =
        multiDrawIndirectEnabled_ &&
        indirectFrame.buffer != VK_NULL_HANDLE &&
        indirectFrame.mapped != nullptr &&
        visibleCommandBytes <=
            indirectFrame.bytes;

    auto* mappedDrawCommands =
        useIndirect
        ? static_cast<
              VkDrawIndexedIndirectCommand*>(
              indirectFrame.mapped)
        : nullptr;

    std::uint32_t activeSubmissionGroupId =
        UINT32_MAX;
    std::uint32_t commandCount = 0U;

    for (const auto& candidate :
         visibleDrawCandidates_) {
        if (candidate.batchIndex >=
            batches_.size()) {
            continue;
        }

        const auto& batch =
            batches_[candidate.batchIndex];

        const std::uint32_t commandIndex =
            commandCount++;

        const auto& draw =
            batch.indirectCommand;
        ++frameStats_.
            precomputedIndirectCommandCopies;

        if (mappedDrawCommands != nullptr) {
            mappedDrawCommands[
                commandIndex] = draw;
            ++frameStats_.
                indirectCommandDirectWrites;
        } else {
            drawCommands_.push_back(draw);
        }

        const std::uint32_t geometryCellSlot =
            cellGeometry
            ? batch.geometryCellSlot
            : UINT32_MAX;

        const bool hasPrecomputedGroup =
            cellGeometry &&
            batch.submissionGroupId !=
                UINT32_MAX;

        const bool startsGroup =
            drawGroups_.empty() ||
            (hasPrecomputedGroup
                ? activeSubmissionGroupId !=
                    batch.submissionGroupId
                : drawGroups_.back().
                        materialIndex !=
                        batch.materialIndex ||
                  drawGroups_.back().
                        geometryCellSlot !=
                        geometryCellSlot ||
                  drawGroups_.back().
                        doubleSided !=
                        batch.doubleSided);

        if (startsGroup) {
            StaticDrawGroup group{};
            group.firstCommand = commandIndex;
            group.materialIndex =
                batch.materialIndex;
            group.geometryCellSlot =
                geometryCellSlot;
            group.doubleSided =
                batch.doubleSided;
            drawGroups_.push_back(group);

            activeSubmissionGroupId =
                hasPrecomputedGroup
                ? batch.submissionGroupId
                : UINT32_MAX;
        }

        ++drawGroups_.back().commandCount;
        ++frameStats_.drawCalls;
        frameStats_.submittedTriangles +=
            static_cast<std::uint64_t>(
                batch.triangleCount);
    }

    frameStats_.submissionGroups =
        static_cast<std::uint32_t>(
            drawGroups_.size());

    for (const auto& group : drawGroups_) {
        if (group.commandCount == 0U ||
            group.materialIndex >=
                materials_.size()) {
            continue;
        }

        if (cellGeometry) {
            if (group.geometryCellSlot >=
                geometryCellCount_) {
                continue;
            }

            const auto& geometryCell =
                geometryCells_[
                    group.geometryCellSlot];

            if (!geometryCell.physicallyResident ||
                geometryCell.vertexBuffer ==
                    VK_NULL_HANDLE ||
                geometryCell.indexBuffer ==
                    VK_NULL_HANDLE) {
                continue;
            }

            if (boundGeometryCell !=
                group.geometryCellSlot) {
                const VkDeviceSize geometryOffset =
                    0U;

                vkCmdBindVertexBuffers(
                    command,
                    0U,
                    1U,
                    &geometryCell.vertexBuffer,
                    &geometryOffset);

                vkCmdBindIndexBuffer(
                    command,
                    geometryCell.indexBuffer,
                    0U,
                    VK_INDEX_TYPE_UINT16);

                boundGeometryCell =
                    group.geometryCellSlot;
                ++frameStats_.geometryBinds;
            }
        }

        const VkPipeline desiredPipeline =
            group.doubleSided
            ? pipelineDoubleSided_
            : pipeline_;

        if (desiredPipeline == VK_NULL_HANDLE) {
            continue;
        }

        if (boundPipeline != desiredPipeline) {
            vkCmdBindPipeline(
                command,
                VK_PIPELINE_BIND_POINT_GRAPHICS,
                desiredPipeline);
            boundPipeline =
                desiredPipeline;
            ++frameStats_.pipelineBinds;
        }

        const auto& material =
            materials_[group.materialIndex];

        if (boundMaterialIndex !=
            group.materialIndex) {
            applyMaterial(material);

            vkCmdBindDescriptorSets(
                command,
                VK_PIPELINE_BIND_POINT_GRAPHICS,
                pipelineLayout_,
                0U,
                1U,
                &material.descriptorSets[
                    frameSlot %
                    kDescriptorFrames],
                0U,
                nullptr);

            boundMaterialIndex =
                group.materialIndex;
            ++frameStats_.materialBinds;
        }

        if (useIndirect) {
            std::uint32_t firstCommand =
                group.firstCommand;
            std::uint32_t remaining =
                group.commandCount;

            while (remaining > 0U) {
                const std::uint32_t chunk =
                    std::min<std::uint32_t>(
                        remaining,
                        maxDrawIndirectCount_);

                const VkDeviceSize offset =
                    static_cast<VkDeviceSize>(
                        firstCommand) *
                    sizeof(VkDrawIndexedIndirectCommand);

                vkCmdDrawIndexedIndirect(
                    command,
                    indirectFrame.buffer,
                    offset,
                    chunk,
                    sizeof(VkDrawIndexedIndirectCommand));

                ++frameStats_.drawSubmissions;
                frameStats_.indirectDraws +=
                    chunk;

                firstCommand += chunk;
                remaining -= chunk;
            }
        } else {
            const std::uint32_t endCommand =
                group.firstCommand +
                group.commandCount;

            for (std::uint32_t i =
                     group.firstCommand;
                 i < endCommand;
                 ++i) {
                const auto& draw =
                    drawCommands_[i];

                vkCmdDrawIndexed(
                    command,
                    draw.indexCount,
                    draw.instanceCount,
                    draw.firstIndex,
                    draw.vertexOffset,
                    draw.firstInstance);

                ++frameStats_.drawSubmissions;
            }
        }
    }

    if (streamCullingActive_ &&
        !streamCullLogged_ &&
        frameStats_.streamingCell != 0U) {
        streamCullLogged_ = true;

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_WORLD_STREAMING_CULL_ACTIVE cell=%u stable_frames=%u cold_batches=%u culled_batches=%u draws=%u draw_submissions=%u indirect_draws=%u indirect_direct_writes=%u precomputed_indirect_commands=%u material_binds=%u geometry_binds=%u pipeline_binds=%u submission_groups=%u multi_draw_indirect=%u portal_tests=%u portal_culled=%u portal_skipped=%u cell_frustum_tests=%u cell_frustum_culled=%u cell_range_skipped=%u cell_frustum_skipped=%u cell_driven_batch_visits=%u batch_frustum_tests=%u material_visibility_tests=%u material_visibility_cache_hits=%u front_to_back_candidates=%u front_to_back_reordered=%u front_to_back_depth_reuses=%u plan_builds=%llu plan_cache_hits=%llu cell_heat_refreshes=%llu projection_cache_hits=%llu",
            static_cast<unsigned int>(
                frameStats_.streamingCell),
            static_cast<unsigned int>(
                streamCellStableFrames_),
            static_cast<unsigned int>(
                frameStats_.
                    streamingColdBatches),
            static_cast<unsigned int>(
                frameStats_.
                    streamingCulledBatches),
            static_cast<unsigned int>(
                frameStats_.drawCalls),
            static_cast<unsigned int>(
                frameStats_.drawSubmissions),
            static_cast<unsigned int>(
                frameStats_.indirectDraws),
            static_cast<unsigned int>(
                frameStats_.
                    indirectCommandDirectWrites),
            static_cast<unsigned int>(
                frameStats_.
                    precomputedIndirectCommandCopies),
            static_cast<unsigned int>(
                frameStats_.materialBinds),
            static_cast<unsigned int>(
                frameStats_.geometryBinds),
            static_cast<unsigned int>(
                frameStats_.pipelineBinds),
            static_cast<unsigned int>(
                frameStats_.submissionGroups),
            useIndirect ? 1U : 0U,
            static_cast<unsigned int>(
                frameStats_.portalVisibilityTests),
            static_cast<unsigned int>(
                frameStats_.portalVisibilityCulled),
            static_cast<unsigned int>(
                frameStats_.portalSkippedBatches),
            static_cast<unsigned int>(
                frameStats_.cellFrustumTests),
            static_cast<unsigned int>(
                frameStats_.cellFrustumCulled),
            static_cast<unsigned int>(
                frameStats_.cellRangeSkippedBatches),
            static_cast<unsigned int>(
                frameStats_.
                    cellFrustumSkippedBatches),
            static_cast<unsigned int>(
                frameStats_.
                    cellDrivenBatchVisits),
            static_cast<unsigned int>(
                frameStats_.batchFrustumTests),
            static_cast<unsigned int>(
                frameStats_.materialVisibilityTests),
            static_cast<unsigned int>(
                frameStats_.
                    materialVisibilityCacheHits),
            static_cast<unsigned int>(
                frameStats_.
                    frontToBackCandidates),
            static_cast<unsigned int>(
                frameStats_.
                    frontToBackReordered),
            static_cast<unsigned int>(
                frameStats_.
                    frontToBackDepthReuses),
            static_cast<unsigned long long>(
                streamPlanBuildCount_),
            static_cast<unsigned long long>(
                streamPlanCacheHitCount_),
            static_cast<unsigned long long>(
                streamCellHeatRefreshCount_),
            static_cast<unsigned long long>(
                worldProjectionCacheHits_));
    }
}

void VulkanStaticMeshRenderer::recordViewmodel(
    VkCommandBuffer command,
    VkExtent2D extent,
    std::uint32_t frameSlot,
    const StaticMeshViewmodelState& state) const noexcept {
    if (!ready_ ||
        command == VK_NULL_HANDLE ||
        extent.width == 0U ||
        extent.height == 0U) {
        return;
    }

    vkCmdBindPipeline(
        command,
        VK_PIPELINE_BIND_POINT_GRAPHICS,
        pipelineDoubleSided_ != VK_NULL_HANDLE
            ? pipelineDoubleSided_
            : pipeline_);

    VkViewport viewport{};
    viewport.width =
        static_cast<float>(extent.width);
    viewport.height =
        static_cast<float>(extent.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;

    VkRect2D scissor{};
    scissor.extent = extent;

    vkCmdSetViewport(
        command,
        0U,
        1U,
        &viewport);

    vkCmdSetScissor(
        command,
        0U,
        1U,
        &scissor);

    PushConstants push{};

    push.viewYawCos =
        std::cos(state.yawRadians);
    push.viewYawSin =
        std::sin(state.yawRadians);
    push.viewPitchCos =
        std::cos(state.pitchRadians);
    push.viewPitchSin =
        std::sin(state.pitchRadians);
    push.viewRollCos =
        std::cos(state.rollRadians);
    push.viewRollSin =
        std::sin(state.rollRadians);

    constexpr float kDegreesToRadians =
        0.01745329251994329577f;
    const float clampedFovDegrees =
        std::clamp(
            state.verticalFovDegrees,
            50.0f,
            110.0f);
    const float projectionFocal =
        1.0f /
        std::tan(
            clampedFovDegrees *
            0.5f *
            kDegreesToRadians);
    const float safeAspect =
        std::max(
            state.aspect,
            0.25f);

    push.projectionFocal =
        projectionFocal;
    push.projectionFocalOverAspect =
        projectionFocal / safeAspect;
    push.modelX = state.x;
    push.modelY = state.y;
    push.modelZ = state.z;
    push.modelScale =
        std::clamp(
            state.scale,
            0.05f,
            8.0f);
    push.lightningFlash = 1.0f;
    push.viewmodelMode = 1U;

    const auto applyMaterial =
        [&](const GpuMaterial& material) noexcept {
            PushConstants materialPush = push;
            materialPush.baseColorFactorR = material.baseColorFactor[0];
            materialPush.baseColorFactorG = material.baseColorFactor[1];
            materialPush.baseColorFactorB = material.baseColorFactor[2];
            materialPush.baseColorFactorA = material.baseColorFactor[3];
            materialPush.metallicFactor =
                material.pushMetallicFactor;
            materialPush.roughnessFactor =
                material.pushRoughnessFactor;
            materialPush.normalScale =
                material.pushNormalScale;
            materialPush.occlusionStrength =
                material.pushOcclusionStrength;
            materialPush.emissiveFactorR = material.emissiveFactor[0];
            materialPush.emissiveFactorG = material.emissiveFactor[1];
            materialPush.emissiveFactorB = material.emissiveFactor[2];

            materialPush.materialFlags =
                material.pushMaterialFlags;

            vkCmdPushConstants(
                command,
                pipelineLayout_,
                VK_SHADER_STAGE_VERTEX_BIT |
                    VK_SHADER_STAGE_FRAGMENT_BIT,
                0U,
                static_cast<std::uint32_t>(
                    sizeof(materialPush)),
                &materialPush);
        };

    if (geometryVertexBuffer_ == VK_NULL_HANDLE ||
        geometryIndexBuffer_ == VK_NULL_HANDLE) {
        return;
    }

    const VkDeviceSize geometryOffset = 0U;

    vkCmdBindVertexBuffers(
        command,
        0U,
        1U,
        &geometryVertexBuffer_,
        &geometryOffset);

    vkCmdBindIndexBuffer(
        command,
        geometryIndexBuffer_,
        0U,
        VK_INDEX_TYPE_UINT16);

    for (const auto& batch : batches_) {
        if (batch.materialIndex >=
            materials_.size()) {
            continue;
        }

        const auto& material =
            materials_[batch.materialIndex];

        applyMaterial(material);

        vkCmdBindDescriptorSets(
            command,
            VK_PIPELINE_BIND_POINT_GRAPHICS,
            pipelineLayout_,
            0U,
            1U,
            &material.descriptorSets[
                frameSlot %
                kDescriptorFrames],
            0U,
            nullptr);

        vkCmdDrawIndexed(
            command,
            batch.indexCount,
            1U,
            batch.firstIndex,
            batch.vertexOffset,
            0U);
    }
}

bool VulkanStaticMeshRenderer::loadModel(
    AAssetManager* assetManager,
    const char* path,
    StaticMeshAsset& out) noexcept {
    AAsset* asset =
        AAssetManager_open(
            assetManager,
            path,
            AASSET_MODE_BUFFER);

    if (asset == nullptr) {
        return false;
    }

    const off_t length =
        AAsset_getLength(asset);

    if (length <= 0 ||
        static_cast<std::uint64_t>(length) >
            256ULL * 1024ULL * 1024ULL) {
        AAsset_close(asset);
        return false;
    }

    const auto parseBytes =
        [&](std::span<const std::byte> byteSpan,
            bool mapped) noexcept {
            const auto result =
                parseStaticMeshXzsm(
                    byteSpan,
                    out);

            if (!result.success) {
                return false;
            }

            StaticMeshDirectory directory{};
            const auto directoryResult =
                parseStaticMeshXzsmDirectory(
                    byteSpan,
                    directory);

            if (!directoryResult.success ||
                directory.batches.size() !=
                    out.batches.size()) {
                out = {};
                return false;
            }

            geometryDirectory_ =
                std::move(directory);
            geometryAssetPath_ =
                path != nullptr
                ? path
                : "";

            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_XZSM_PARSE_SOURCE path=%s mapped=%u bytes_mb=%.2f heap_copy_mb=%.2f",
                path != nullptr
                    ? path
                    : "",
                mapped ? 1U : 0U,
                static_cast<double>(
                    byteSpan.size()) /
                    (1024.0 * 1024.0),
                mapped
                    ? 0.0
                    : static_cast<double>(
                          byteSpan.size()) /
                          (1024.0 * 1024.0));

            return true;
        };

    const void* mapped =
        AAsset_getBuffer(asset);

    if (mapped != nullptr) {
        const auto byteSpan =
            std::span<const std::byte>(
                static_cast<const std::byte*>(
                    mapped),
                static_cast<std::size_t>(
                    length));

        const bool parsed =
            parseBytes(
                byteSpan,
                true);

        AAsset_close(asset);
        return parsed;
    }

    std::vector<std::byte> bytes;

    try {
        bytes.resize(
            static_cast<std::size_t>(
                length));
    } catch (...) {
        AAsset_close(asset);
        return false;
    }

    const int read =
        AAsset_read(
            asset,
            bytes.data(),
            bytes.size());

    AAsset_close(asset);

    if (read < 0 ||
        static_cast<std::size_t>(read) !=
            bytes.size()) {
        return false;
    }

    return parseBytes(
        std::span<const std::byte>(
            bytes.data(),
            bytes.size()),
        false);
}

bool VulkanStaticMeshRenderer::createPipeline(
    AAssetManager* assetManager) noexcept {
    VkShaderModule vertex = VK_NULL_HANDLE;
    VkShaderModule fragment = VK_NULL_HANDLE;

    if (!createShaderModule(
            assetManager,
            "shaders/xziel_static_mesh.vert.spv",
            vertex) ||
        !createShaderModule(
            assetManager,
            "shaders/xziel_static_mesh.frag.spv",
            fragment)) {
        if (vertex != VK_NULL_HANDLE) {
            vkDestroyShaderModule(
                device_, vertex, nullptr);
        }
        if (fragment != VK_NULL_HANDLE) {
            vkDestroyShaderModule(
                device_, fragment, nullptr);
        }
        return false;
    }

    std::array<VkDescriptorSetLayoutBinding, 4>
        textureBindings{};

    for (std::uint32_t binding = 0U;
         binding < textureBindings.size();
         ++binding) {
        textureBindings[binding].binding = binding;
        textureBindings[binding].descriptorType =
            VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        textureBindings[binding].descriptorCount = 1U;
        textureBindings[binding].stageFlags =
            VK_SHADER_STAGE_FRAGMENT_BIT;
    }

    VkDescriptorSetLayoutCreateInfo setInfo{
        VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO
    };
    setInfo.bindingCount =
        static_cast<std::uint32_t>(
            textureBindings.size());
    setInfo.pBindings =
        textureBindings.data();

    if (!ok(
            vkCreateDescriptorSetLayout(
                device_,
                &setInfo,
                nullptr,
                &descriptorSetLayout_))) {
        vkDestroyShaderModule(
            device_, fragment, nullptr);
        vkDestroyShaderModule(
            device_, vertex, nullptr);
        return false;
    }

    VkPushConstantRange pushRange{};
    pushRange.stageFlags =
        VK_SHADER_STAGE_VERTEX_BIT |
        VK_SHADER_STAGE_FRAGMENT_BIT;
    pushRange.offset = 0U;
    pushRange.size =
        static_cast<std::uint32_t>(
            sizeof(PushConstants));

    VkPipelineLayoutCreateInfo layoutInfo{
        VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO
    };
    layoutInfo.setLayoutCount = 1U;
    layoutInfo.pSetLayouts =
        &descriptorSetLayout_;
    layoutInfo.pushConstantRangeCount = 1U;
    layoutInfo.pPushConstantRanges =
        &pushRange;

    if (!ok(
            vkCreatePipelineLayout(
                device_,
                &layoutInfo,
                nullptr,
                &pipelineLayout_))) {
        vkDestroyShaderModule(
            device_, fragment, nullptr);
        vkDestroyShaderModule(
            device_, vertex, nullptr);
        return false;
    }

    const std::array<VkPipelineShaderStageCreateInfo, 2>
        stages{{
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0U,
                VK_SHADER_STAGE_VERTEX_BIT,
                vertex,
                "main",
                nullptr,
            },
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0U,
                VK_SHADER_STAGE_FRAGMENT_BIT,
                fragment,
                "main",
                nullptr,
            },
        }};

    VkVertexInputBindingDescription binding{};
    binding.binding = 0U;
    binding.stride =
        static_cast<std::uint32_t>(
            gpuStaticVertexStride(
                packedStaticVertexEnabled_));
    binding.inputRate =
        VK_VERTEX_INPUT_RATE_VERTEX;

    std::array<
        VkVertexInputAttributeDescription,
        3> attributes{};

    attributes[0] = {
        0U,
        0U,
        VK_FORMAT_R32G32B32_SFLOAT,
        0U,
    };

    if (packedStaticVertexEnabled_) {
        attributes[1] = {
            1U,
            0U,
            VK_FORMAT_R16G16B16A16_SNORM,
            static_cast<std::uint32_t>(
                offsetof(
                    PackedStaticMeshVertex,
                    normal)),
        };

        attributes[2] = {
            2U,
            0U,
            VK_FORMAT_R16G16_UNORM,
            static_cast<std::uint32_t>(
                offsetof(
                    PackedStaticMeshVertex,
                    uv)),
        };
    } else {
        attributes[1] = {
            1U,
            0U,
            VK_FORMAT_R32G32B32_SFLOAT,
            static_cast<std::uint32_t>(
                offsetof(
                    StaticMeshVertex,
                    nx)),
        };

        attributes[2] = {
            2U,
            0U,
            VK_FORMAT_R32G32_SFLOAT,
            static_cast<std::uint32_t>(
                offsetof(
                    StaticMeshVertex,
                    u)),
        };
    }

    VkPipelineVertexInputStateCreateInfo vertexInput{
        VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO
    };
    vertexInput.vertexBindingDescriptionCount = 1U;
    vertexInput.pVertexBindingDescriptions =
        &binding;
    vertexInput.vertexAttributeDescriptionCount =
        static_cast<std::uint32_t>(
            attributes.size());
    vertexInput.pVertexAttributeDescriptions =
        attributes.data();

    VkPipelineInputAssemblyStateCreateInfo inputAssembly{
        VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO
    };
    inputAssembly.topology =
        VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;

    VkPipelineViewportStateCreateInfo viewportState{
        VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO
    };
    viewportState.viewportCount = 1U;
    viewportState.scissorCount = 1U;

    VkPipelineRasterizationStateCreateInfo raster{
        VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO
    };
    raster.polygonMode =
        VK_POLYGON_MODE_FILL;
    raster.cullMode =
        VK_CULL_MODE_NONE;
    raster.frontFace =
        VK_FRONT_FACE_COUNTER_CLOCKWISE;
    raster.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo multisample{
        VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO
    };
    multisample.rasterizationSamples =
        sampleCount_;

    VkPipelineDepthStencilStateCreateInfo depthStencil{
        VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO
    };
    depthStencil.depthTestEnable = VK_TRUE;
    depthStencil.depthWriteEnable = VK_TRUE;
    depthStencil.depthCompareOp =
        VK_COMPARE_OP_LESS_OR_EQUAL;

    VkPipelineColorBlendAttachmentState attachment{};
    attachment.colorWriteMask =
        VK_COLOR_COMPONENT_R_BIT |
        VK_COLOR_COMPONENT_G_BIT |
        VK_COLOR_COMPONENT_B_BIT |
        VK_COLOR_COMPONENT_A_BIT;

    VkPipelineColorBlendStateCreateInfo blend{
        VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO
    };
    blend.attachmentCount = 1U;
    blend.pAttachments = &attachment;

    constexpr std::array<VkDynamicState, 2>
        dynamicStates{{
            VK_DYNAMIC_STATE_VIEWPORT,
            VK_DYNAMIC_STATE_SCISSOR,
        }};

    VkPipelineDynamicStateCreateInfo dynamic{
        VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO
    };
    dynamic.dynamicStateCount =
        static_cast<std::uint32_t>(
            dynamicStates.size());
    dynamic.pDynamicStates =
        dynamicStates.data();

    VkGraphicsPipelineCreateInfo info{
        VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO
    };
    info.stageCount =
        static_cast<std::uint32_t>(
            stages.size());
    info.pStages = stages.data();
    info.pVertexInputState = &vertexInput;
    info.pInputAssemblyState = &inputAssembly;
    info.pViewportState = &viewportState;
    info.pRasterizationState = &raster;
    info.pMultisampleState = &multisample;
    info.pDepthStencilState = &depthStencil;
    info.pColorBlendState = &blend;
    info.pDynamicState = &dynamic;
    info.layout = pipelineLayout_;
    info.renderPass = renderPass_;
    info.subpass = 0U;

    // glTF's default is single-sided: back-face culling enabled.
    raster.cullMode =
        VK_CULL_MODE_BACK_BIT;

    const VkResult culledResult =
        vkCreateGraphicsPipelines(
            device_,
            VK_NULL_HANDLE,
            1U,
            &info,
            nullptr,
            &pipeline_);

    VkResult doubleSidedResult =
        VK_ERROR_INITIALIZATION_FAILED;

    if (ok(culledResult)) {
        raster.cullMode =
            VK_CULL_MODE_NONE;

        doubleSidedResult =
            vkCreateGraphicsPipelines(
                device_,
                VK_NULL_HANDLE,
                1U,
                &info,
                nullptr,
                &pipelineDoubleSided_);
    }

    vkDestroyShaderModule(
        device_, fragment, nullptr);
    vkDestroyShaderModule(
        device_, vertex, nullptr);

    return
        ok(culledResult) &&
        ok(doubleSidedResult);
}

bool VulkanStaticMeshRenderer::createBuffer(
    VkDeviceSize size,
    VkBufferUsageFlags usage,
    VkMemoryPropertyFlags memoryFlags,
    VkBuffer& buffer,
    VkDeviceMemory& memory) noexcept {
    if (size == 0U) {
        return false;
    }

    VkBufferCreateInfo info{
        VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO
    };
    info.size = size;
    info.usage = usage;
    info.sharingMode =
        VK_SHARING_MODE_EXCLUSIVE;

    if (!ok(
            vkCreateBuffer(
                device_,
                &info,
                nullptr,
                &buffer))) {
        return false;
    }

    VkMemoryRequirements requirements{};
    vkGetBufferMemoryRequirements(
        device_,
        buffer,
        &requirements);

    std::uint32_t typeIndex = 0U;

    if (!findMemoryType(
            requirements.memoryTypeBits,
            memoryFlags,
            typeIndex)) {
        vkDestroyBuffer(
            device_, buffer, nullptr);
        buffer = VK_NULL_HANDLE;
        return false;
    }

    VkMemoryAllocateInfo allocation{
        VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO
    };
    allocation.allocationSize =
        requirements.size;
    allocation.memoryTypeIndex =
        typeIndex;

    if (!ok(
            vkAllocateMemory(
                device_,
                &allocation,
                nullptr,
                &memory))) {
        vkDestroyBuffer(
            device_, buffer, nullptr);
        buffer = VK_NULL_HANDLE;
        return false;
    }

    if (!ok(
            vkBindBufferMemory(
                device_,
                buffer,
                memory,
                0U))) {
        vkFreeMemory(
            device_, memory, nullptr);
        vkDestroyBuffer(
            device_, buffer, nullptr);
        memory = VK_NULL_HANDLE;
        buffer = VK_NULL_HANDLE;
        return false;
    }

    return true;
}

bool VulkanStaticMeshRenderer::createGeometryResidency(
    const StaticMeshAsset& asset,
    const std::vector<std::uint32_t>& materialIndices) noexcept {
    destroyGeometryResidency();

    if (asset.batches.empty() ||
        materialIndices.size() !=
            asset.batches.size() ||
        asset.totalVertices == 0U ||
        asset.totalIndices == 0U ||
        asset.totalVertices >
            static_cast<std::uint32_t>(
                std::numeric_limits<std::int32_t>::max())) {
        return false;
    }

    if (streamGraphReady_) {
        geometryCells_ = {};
        geometryCellCount_ = 0U;
        geometryCellVertexBytes_ = 0U;
        geometryCellIndexBytes_ = 0U;

        const auto findCellSlot =
            [&](std::uint32_t cellId) noexcept
                -> std::uint32_t {
                for (std::size_t i = 0U;
                     i < geometryCellCount_;
                     ++i) {
                    if (geometryCells_[i].cellId ==
                        cellId) {
                        return
                            static_cast<std::uint32_t>(i);
                    }
                }

                return UINT32_MAX;
            };

        for (const auto& batch :
             asset.batches) {
            const std::uint32_t cellId =
                static_cast<std::uint32_t>(
                    sanctumZoneForAssetName(
                        batch.textureName));

            std::uint32_t slot =
                findCellSlot(cellId);

            if (slot == UINT32_MAX) {
                if (geometryCellCount_ >=
                    geometryCells_.size()) {
                    destroyGeometryResidency();
                    return false;
                }

                slot =
                    static_cast<std::uint32_t>(
                        geometryCellCount_++);

                geometryCells_[slot].cellId =
                    cellId;
                geometryCells_[slot].pinned =
                    cellId == 0U;
            }

            auto& cell =
                geometryCells_[slot];

            if (batch.vertices.size() >
                    std::numeric_limits<
                        std::uint32_t>::max() -
                    cell.vertexCount ||
                batch.indices.size() >
                    std::numeric_limits<
                        std::uint32_t>::max() -
                    cell.indexCount) {
                destroyGeometryResidency();
                return false;
            }

            cell.vertexCount +=
                static_cast<std::uint32_t>(
                    batch.vertices.size());
            cell.indexCount +=
                static_cast<std::uint32_t>(
                    batch.indices.size());
        }

        const VkMemoryPropertyFlags hostFlags =
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
            VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;

        const VkMemoryPropertyFlags preferredFlags =
            hostFlags |
            VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;

        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            auto& cell =
                geometryCells_[i];

            cell.vertexBytes =
                static_cast<VkDeviceSize>(
                    cell.vertexCount) *
                static_cast<VkDeviceSize>(
                    gpuStaticVertexStride(
                        packedStaticVertexEnabled_));
            cell.indexBytes =
                static_cast<VkDeviceSize>(
                    cell.indexCount) *
                sizeof(std::uint16_t);

            if (cell.vertexBytes == 0U ||
                cell.indexBytes == 0U ||
                cell.vertexCount >
                    static_cast<std::uint32_t>(
                        std::numeric_limits<
                            std::int32_t>::max())) {
                destroyGeometryResidency();
                return false;
            }

            const auto destroyCell =
                [&]() noexcept {
                    if (cell.indexBuffer !=
                        VK_NULL_HANDLE) {
                        vkDestroyBuffer(
                            device_,
                            cell.indexBuffer,
                            nullptr);
                        cell.indexBuffer =
                            VK_NULL_HANDLE;
                    }

                    if (cell.indexMemory !=
                        VK_NULL_HANDLE) {
                        vkFreeMemory(
                            device_,
                            cell.indexMemory,
                            nullptr);
                        cell.indexMemory =
                            VK_NULL_HANDLE;
                    }

                    if (cell.vertexBuffer !=
                        VK_NULL_HANDLE) {
                        vkDestroyBuffer(
                            device_,
                            cell.vertexBuffer,
                            nullptr);
                        cell.vertexBuffer =
                            VK_NULL_HANDLE;
                    }

                    if (cell.vertexMemory !=
                        VK_NULL_HANDLE) {
                        vkFreeMemory(
                            device_,
                            cell.vertexMemory,
                            nullptr);
                        cell.vertexMemory =
                            VK_NULL_HANDLE;
                    }
                };

            const auto createPair =
                [&](VkMemoryPropertyFlags flags)
                    noexcept {
                    if (!createBuffer(
                            cell.vertexBytes,
                            VK_BUFFER_USAGE_VERTEX_BUFFER_BIT |
                                VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                            flags,
                            cell.vertexBuffer,
                            cell.vertexMemory)) {
                        return false;
                    }

                    if (!createBuffer(
                            cell.indexBytes,
                            VK_BUFFER_USAGE_INDEX_BUFFER_BIT |
                                VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                            flags,
                            cell.indexBuffer,
                            cell.indexMemory)) {
                        destroyCell();
                        return false;
                    }

                    return true;
                };

            cell.deviceLocalHostVisible =
                createPair(preferredFlags);

            if (!cell.deviceLocalHostVisible &&
                !createPair(hostFlags)) {
                destroyGeometryResidency();
                return false;
            }

            cell.physicallyResident = true;
            geometryCellVertexBytes_ +=
                cell.vertexBytes;
            geometryCellIndexBytes_ +=
                cell.indexBytes;
        }

        std::array<void*, kMaxStreamCells + 1U>
            mappedVertices{};
        std::array<void*, kMaxStreamCells + 1U>
            mappedIndices{};
        std::array<std::uint64_t, kMaxStreamCells + 1U>
            vertexCursor{};
        std::array<std::uint64_t, kMaxStreamCells + 1U>
            indexCursor{};

        const auto unmapCells =
            [&]() noexcept {
                for (std::size_t i = 0U;
                     i < geometryCellCount_;
                     ++i) {
                    if (mappedVertices[i] != nullptr &&
                        geometryCells_[i].vertexMemory !=
                            VK_NULL_HANDLE) {
                        vkUnmapMemory(
                            device_,
                            geometryCells_[i].
                                vertexMemory);
                        mappedVertices[i] = nullptr;
                    }

                    if (mappedIndices[i] != nullptr &&
                        geometryCells_[i].indexMemory !=
                            VK_NULL_HANDLE) {
                        vkUnmapMemory(
                            device_,
                            geometryCells_[i].
                                indexMemory);
                        mappedIndices[i] = nullptr;
                    }
                }
            };

        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            auto& cell =
                geometryCells_[i];

            if (!ok(
                    vkMapMemory(
                        device_,
                        cell.vertexMemory,
                        0U,
                        cell.vertexBytes,
                        0U,
                        &mappedVertices[i])) ||
                !ok(
                    vkMapMemory(
                        device_,
                        cell.indexMemory,
                        0U,
                        cell.indexBytes,
                        0U,
                        &mappedIndices[i]))) {
                unmapCells();
                destroyGeometryResidency();
                return false;
            }
        }

        try {
            batches_.clear();
            batches_.reserve(
                asset.batches.size());

            for (std::size_t batchIndex = 0U;
                 batchIndex < asset.batches.size();
                 ++batchIndex) {
                const auto& batch =
                    asset.batches[batchIndex];

                const std::uint32_t cellId =
                    static_cast<std::uint32_t>(
                        sanctumZoneForAssetName(
                            batch.textureName));

                const std::uint32_t slot =
                    findCellSlot(cellId);

                if (slot == UINT32_MAX ||
                    batch.vertices.empty() ||
                    batch.indices.empty()) {
                    unmapCells();
                    destroyGeometryResidency();
                    return false;
                }

                auto& cell =
                    geometryCells_[slot];

                if (vertexCursor[slot] +
                        batch.vertices.size() >
                    cell.vertexCount ||
                    indexCursor[slot] +
                        batch.indices.size() >
                    cell.indexCount) {
                    unmapCells();
                    destroyGeometryResidency();
                    return false;
                }

                const VkDeviceSize vertexOffsetBytes =
                    static_cast<VkDeviceSize>(
                        vertexCursor[slot]) *
                    static_cast<VkDeviceSize>(
                        gpuStaticVertexStride(
                            packedStaticVertexEnabled_));

                const VkDeviceSize indexOffsetBytes =
                    static_cast<VkDeviceSize>(
                        indexCursor[slot]) *
                    sizeof(std::uint16_t);

                writeGpuVertices(
                    std::span<const StaticMeshVertex>(
                        batch.vertices.data(),
                        batch.vertices.size()),
                    static_cast<std::byte*>(
                        mappedVertices[slot]) +
                        vertexOffsetBytes,
                    packedStaticVertexEnabled_);

                std::memcpy(
                    static_cast<std::byte*>(
                        mappedIndices[slot]) +
                        indexOffsetBytes,
                    batch.indices.data(),
                    batch.indices.size() *
                        sizeof(std::uint16_t));

                GpuBatch gpuBatch{};
                gpuBatch.materialIndex =
                    materialIndices[batchIndex];

                if (gpuBatch.materialIndex <
                    materials_.size()) {
                    gpuBatch.streamResourceId =
                        materials_[
                            gpuBatch.materialIndex].
                                streamResourceId;
                }

                gpuBatch.streamCellId =
                    cellId;
                gpuBatch.geometryCellSlot =
                    slot;
                gpuBatch.sourceBatchIndex =
                    static_cast<std::uint32_t>(
                        batchIndex);
                gpuBatch.firstIndex =
                    static_cast<std::uint32_t>(
                        indexCursor[slot]);
                gpuBatch.vertexOffset =
                    static_cast<std::int32_t>(
                        vertexCursor[slot]);
                gpuBatch.indexCount =
                    static_cast<std::uint32_t>(
                        batch.indices.size());
                gpuBatch.triangleCount =
                    gpuBatch.indexCount / 3U;
                gpuBatch.indirectCommand.indexCount =
                    gpuBatch.indexCount;
                gpuBatch.indirectCommand.instanceCount = 1U;
                gpuBatch.indirectCommand.firstIndex =
                    gpuBatch.firstIndex;
                gpuBatch.indirectCommand.vertexOffset =
                    gpuBatch.vertexOffset;
                gpuBatch.indirectCommand.firstInstance = 0U;
                gpuBatch.bounds =
                    batch.bounds;
                cacheGpuBatchCullingSphere(
                    gpuBatch);
                gpuBatch.doubleSided =
                    batch.doubleSided();

                batches_.emplace_back(
                    gpuBatch);

                vertexCursor[slot] +=
                    batch.vertices.size();
                indexCursor[slot] +=
                    batch.indices.size();
            }
        } catch (...) {
            unmapCells();
            destroyGeometryResidency();
            return false;
        }

        unmapCells();

        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            if (vertexCursor[i] !=
                    geometryCells_[i].
                        vertexCount ||
                indexCursor[i] !=
                    geometryCells_[i].
                        indexCount) {
                destroyGeometryResidency();
                return false;
            }
        }

        std::stable_sort(
            batches_.begin(),
            batches_.end(),
            [](const GpuBatch& a,
               const GpuBatch& b) noexcept {
                if (a.geometryCellSlot !=
                    b.geometryCellSlot) {
                    return
                        a.geometryCellSlot <
                        b.geometryCellSlot;
                }

                if (a.materialIndex !=
                    b.materialIndex) {
                    return
                        a.materialIndex <
                        b.materialIndex;
                }

                if (a.doubleSided !=
                    b.doubleSided) {
                    return
                        a.doubleSided <
                        b.doubleSided;
                }

                return
                    a.sourceBatchIndex <
                    b.sourceBatchIndex;
            });

        std::uint32_t submissionGroupCount = 0U;

        for (std::size_t batchIndex = 0U;
             batchIndex < batches_.size();
             ++batchIndex) {
            auto& batch =
                batches_[batchIndex];

            if (batchIndex > 0U) {
                const auto& previous =
                    batches_[batchIndex - 1U];

                if (batch.geometryCellSlot !=
                        previous.geometryCellSlot ||
                    batch.materialIndex !=
                        previous.materialIndex ||
                    batch.doubleSided !=
                        previous.doubleSided) {
                    ++submissionGroupCount;
                }
            }

            batch.submissionGroupId =
                submissionGroupCount;
        }

        if (!batches_.empty()) {
            ++submissionGroupCount;
        }

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_STATIC_SUBMISSION_GROUPS_READY groups=%u batches=%u",
            static_cast<unsigned int>(
                submissionGroupCount),
            static_cast<unsigned int>(
                batches_.size()));

        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            geometryCells_[i].firstBatch =
                UINT32_MAX;
            geometryCells_[i].batchCount = 0U;
        }

        for (std::uint32_t batchIndex = 0U;
             batchIndex <
                 static_cast<std::uint32_t>(
                     batches_.size());
             ++batchIndex) {
            const auto& batch =
                batches_[batchIndex];

            if (batch.geometryCellSlot >=
                geometryCellCount_) {
                destroyGeometryResidency();
                return false;
            }

            auto& cell =
                geometryCells_[
                    batch.geometryCellSlot];

            if (cell.firstBatch ==
                UINT32_MAX) {
                cell.firstBatch =
                    batchIndex;
            }

            ++cell.batchCount;
        }

        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            const auto& cell =
                geometryCells_[i];

            if (cell.firstBatch ==
                    UINT32_MAX ||
                cell.batchCount == 0U ||
                static_cast<std::uint64_t>(
                    cell.firstBatch) +
                    static_cast<std::uint64_t>(
                        cell.batchCount) >
                    batches_.size()) {
                destroyGeometryResidency();
                return false;
            }
        }

        rebuildStreamingCellBounds();

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_CULL_SPHERES_READY batches=%u cells=%u",
            static_cast<unsigned int>(
                batches_.size()),
            static_cast<unsigned int>(
                geometryCellCount_));

        std::uint32_t pinnedCells = 0U;
        std::uint32_t localCells = 0U;

        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            pinnedCells +=
                geometryCells_[i].pinned
                ? 1U
                : 0U;
            localCells +=
                geometryCells_[i].
                    deviceLocalHostVisible
                ? 1U
                : 0U;
        }

        geometryResidentBytes_ =
            static_cast<std::uint64_t>(
                geometryCellVertexBytes_ +
                geometryCellIndexBytes_);

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_GEOMETRY_HEAT_EVENT_DRIVEN_READY cells=%u",
            static_cast<unsigned int>(
                geometryCellCount_));

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_STREAM_GEOMETRY_CELLS_READY cells=%u buffers=%u pinned=%u vertex_mb=%.2f index_mb=%.2f device_local_host_visible=%u",
            static_cast<unsigned int>(
                geometryCellCount_),
            static_cast<unsigned int>(
                geometryCellCount_ * 2U),
            static_cast<unsigned int>(
                pinnedCells),
            static_cast<double>(
                geometryCellVertexBytes_) /
                (1024.0 * 1024.0),
            static_cast<double>(
                geometryCellIndexBytes_) /
                (1024.0 * 1024.0),
            static_cast<unsigned int>(
                localCells));

        return true;
    }

    geometryVertexBytes_ =
        static_cast<VkDeviceSize>(
            asset.totalVertices) *
        static_cast<VkDeviceSize>(
            gpuStaticVertexStride(
                packedStaticVertexEnabled_));

    geometryIndexBytes_ =
        static_cast<VkDeviceSize>(
            asset.totalIndices) *
        sizeof(std::uint16_t);

    const VkMemoryPropertyFlags hostFlags =
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
        VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;

    const VkMemoryPropertyFlags preferredFlags =
        hostFlags |
        VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;

    const auto destroyPartial =
        [&]() noexcept {
            if (geometryIndexBuffer_ != VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    geometryIndexBuffer_,
                    nullptr);
                geometryIndexBuffer_ =
                    VK_NULL_HANDLE;
            }

            if (geometryIndexMemory_ != VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    geometryIndexMemory_,
                    nullptr);
                geometryIndexMemory_ =
                    VK_NULL_HANDLE;
            }

            if (geometryVertexBuffer_ != VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    geometryVertexBuffer_,
                    nullptr);
                geometryVertexBuffer_ =
                    VK_NULL_HANDLE;
            }

            if (geometryVertexMemory_ != VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    geometryVertexMemory_,
                    nullptr);
                geometryVertexMemory_ =
                    VK_NULL_HANDLE;
            }
        };

    auto createPair =
        [&](VkMemoryPropertyFlags flags) noexcept {
            if (!createBuffer(
                    geometryVertexBytes_,
                    VK_BUFFER_USAGE_VERTEX_BUFFER_BIT |
                        VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                    flags,
                    geometryVertexBuffer_,
                    geometryVertexMemory_)) {
                return false;
            }

            if (!createBuffer(
                    geometryIndexBytes_,
                    VK_BUFFER_USAGE_INDEX_BUFFER_BIT |
                        VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                    flags,
                    geometryIndexBuffer_,
                    geometryIndexMemory_)) {
                destroyPartial();
                return false;
            }

            return true;
        };

    geometryDeviceLocalHostVisible_ =
        createPair(preferredFlags);

    if (!geometryDeviceLocalHostVisible_ &&
        !createPair(hostFlags)) {
        geometryVertexBytes_ = 0U;
        geometryIndexBytes_ = 0U;
        return false;
    }

    void* mappedVertices = nullptr;
    void* mappedIndices = nullptr;

    if (!ok(
            vkMapMemory(
                device_,
                geometryVertexMemory_,
                0U,
                geometryVertexBytes_,
                0U,
                &mappedVertices)) ||
        !ok(
            vkMapMemory(
                device_,
                geometryIndexMemory_,
                0U,
                geometryIndexBytes_,
                0U,
                &mappedIndices))) {
        if (mappedVertices != nullptr) {
            vkUnmapMemory(
                device_,
                geometryVertexMemory_);
        }
        destroyGeometryResidency();
        return false;
    }

    auto* vertexBytes =
        static_cast<std::byte*>(
            mappedVertices);

    auto* indexBytes =
        static_cast<std::byte*>(
            mappedIndices);

    std::uint64_t vertexCursor = 0U;
    std::uint64_t indexCursor = 0U;

    try {
        batches_.clear();
        batches_.reserve(
            asset.batches.size());

        for (std::size_t batchIndex = 0U;
             batchIndex < asset.batches.size();
             ++batchIndex) {
            const auto& batch =
                asset.batches[batchIndex];

            if (batch.vertices.empty() ||
                batch.indices.empty() ||
                vertexCursor +
                        batch.vertices.size() >
                    asset.totalVertices ||
                indexCursor +
                        batch.indices.size() >
                    asset.totalIndices) {
                vkUnmapMemory(
                    device_,
                    geometryIndexMemory_);
                vkUnmapMemory(
                    device_,
                    geometryVertexMemory_);
                destroyGeometryResidency();
                return false;
            }

            const VkDeviceSize vertexOffsetBytes =
                static_cast<VkDeviceSize>(
                    vertexCursor) *
                static_cast<VkDeviceSize>(
                    gpuStaticVertexStride(
                        packedStaticVertexEnabled_));

            const VkDeviceSize indexOffsetBytes =
                static_cast<VkDeviceSize>(
                    indexCursor) *
                sizeof(std::uint16_t);

            writeGpuVertices(
                std::span<const StaticMeshVertex>(
                    batch.vertices.data(),
                    batch.vertices.size()),
                vertexBytes +
                    vertexOffsetBytes,
                packedStaticVertexEnabled_);

            std::memcpy(
                indexBytes +
                    indexOffsetBytes,
                batch.indices.data(),
                batch.indices.size() *
                    sizeof(std::uint16_t));

            GpuBatch gpuBatch{};
            gpuBatch.materialIndex =
                materialIndices[batchIndex];

            if (gpuBatch.materialIndex <
                materials_.size()) {
                gpuBatch.streamResourceId =
                    materials_[
                        gpuBatch.materialIndex].
                            streamResourceId;
            }

            gpuBatch.streamCellId =
                static_cast<std::uint32_t>(
                    sanctumZoneForAssetName(
                        batch.textureName));
            gpuBatch.firstIndex =
                static_cast<std::uint32_t>(
                    indexCursor);
            gpuBatch.vertexOffset =
                static_cast<std::int32_t>(
                    vertexCursor);
            gpuBatch.indexCount =
                static_cast<std::uint32_t>(
                    batch.indices.size());
            gpuBatch.triangleCount =
                gpuBatch.indexCount / 3U;
            gpuBatch.indirectCommand.indexCount =
                gpuBatch.indexCount;
            gpuBatch.indirectCommand.instanceCount = 1U;
            gpuBatch.indirectCommand.firstIndex =
                gpuBatch.firstIndex;
            gpuBatch.indirectCommand.vertexOffset =
                gpuBatch.vertexOffset;
            gpuBatch.indirectCommand.firstInstance = 0U;
            gpuBatch.bounds =
                batch.bounds;
            cacheGpuBatchCullingSphere(
                gpuBatch);
            gpuBatch.doubleSided =
                batch.doubleSided();

            batches_.emplace_back(
                gpuBatch);

            vertexCursor +=
                batch.vertices.size();

            indexCursor +=
                batch.indices.size();
        }
    } catch (...) {
        vkUnmapMemory(
            device_,
            geometryIndexMemory_);
        vkUnmapMemory(
            device_,
            geometryVertexMemory_);
        destroyGeometryResidency();
        return false;
    }

    vkUnmapMemory(
        device_,
        geometryIndexMemory_);

    vkUnmapMemory(
        device_,
        geometryVertexMemory_);

    if (vertexCursor != asset.totalVertices ||
        indexCursor != asset.totalIndices) {
        destroyGeometryResidency();
        return false;
    }

    rebuildStreamingCellBounds();

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_CULL_SPHERES_READY batches=%u",
        static_cast<unsigned int>(
            batches_.size()));

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STATIC_GEOMETRY_RESIDENCY buffers=2 batches=%u vertex_mb=%.2f index_mb=%.2f device_local_host_visible=%d",
        static_cast<unsigned int>(
            batches_.size()),
        static_cast<double>(
            geometryVertexBytes_) /
            (1024.0 * 1024.0),
        static_cast<double>(
            geometryIndexBytes_) /
            (1024.0 * 1024.0),
        geometryDeviceLocalHostVisible_
            ? 1
            : 0);

    return true;
}

bool VulkanStaticMeshRenderer::createTexture(
    AAssetManager* assetManager,
    const std::string& exportedName,
    bool srgb,
    GpuTexture& out) noexcept {
    // EXACT_ST_GILES_PNG_RUNTIME_REFERENCE_V1
    // The exterior albedo is the comparison authority.  During this audit,
    // load its exact GLB-decoded PNG instead of the ASTC derivative.  Normal,
    // ORM and detail maps are linear (srgb=false), so they are not caught by
    // this reference-only branch.
    const bool exactExteriorReference =
        isExactStGilesExteriorReference(
            exportedName,
            srgb);

    if (exactExteriorReference) {
        const std::string pngPath =
            textureAssetPath(
                exportedName,
                ".png");

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_EXTERIOR_SOURCE_PNG_FIDELITY_ACTIVE path=%s",
            pngPath.c_str());

        return createPngTexture(
            assetManager,
            pngPath,
            true,
            out);
    }

    const std::string ktxPath =
        textureAssetPath(
            exportedName,
            ".ktx2");

    if (astcLdrSupported_ &&
        assetExists(
            assetManager,
            ktxPath)) {
        if (!createKtx2Texture(
                assetManager,
                ktxPath,
                srgb,
                out)) {
            logError(
                "ASTC KTX2 texture exists but failed validation/upload");
            return false;
        }

        return true;
    }

    const std::string pngPath =
        textureAssetPath(
            exportedName,
            ".png");

    return createPngTexture(
        assetManager,
        pngPath,
        srgb,
        out);
}

bool VulkanStaticMeshRenderer::createKtx2Texture(
    AAssetManager* assetManager,
    const std::string& assetPath,
    bool srgb,
    GpuTexture& out) noexcept {
    std::vector<std::byte> bytes;

    const bool asyncRead =
        assetStreamer_.take(
            assetPath,
            bytes);

    if (!asyncRead) {
        AAsset* asset =
            AAssetManager_open(
                assetManager,
                assetPath.c_str(),
                AASSET_MODE_BUFFER);

        if (asset == nullptr) {
            return false;
        }

        const off_t length =
            AAsset_getLength(asset);

        if (length <= 0 ||
            static_cast<std::uint64_t>(length) >
                256ULL * 1024ULL * 1024ULL) {
            AAsset_close(asset);
            return false;
        }

        try {
            bytes.resize(
                static_cast<std::size_t>(
                    length));
        } catch (...) {
            AAsset_close(asset);
            return false;
        }

        const int read =
            AAsset_read(
                asset,
                bytes.data(),
                bytes.size());

        AAsset_close(asset);

        if (read < 0 ||
            static_cast<std::size_t>(read) !=
                bytes.size()) {
            return false;
        }
    }

    Ktx2Texture texture{};
    const auto parsed =
        parseKtx2Astc(
            std::span<const std::byte>(
                bytes.data(),
                bytes.size()),
            texture);

    if (!parsed.success ||
        texture.levels.empty() ||
        texture.srgb != srgb) {
        return false;
    }

    const VkFormat textureFormat =
        static_cast<VkFormat>(
            texture.vkFormat);

    VkFormatProperties properties{};
    vkGetPhysicalDeviceFormatProperties(
        physicalDevice_,
        textureFormat,
        &properties);

    if ((properties.optimalTilingFeatures &
         VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT) == 0U) {
        return false;
    }

    std::uint32_t residentBaseMip = 0U;

    const auto fullRange =
        planKtx2ResidentMipRange(
            texture,
            0U);

    if (!fullRange.valid) {
        return false;
    }

    const std::uint64_t budgetRemaining =
        textureResidentBytes_ <
                textureResidentBudgetBytes_
        ? textureResidentBudgetBytes_ -
            textureResidentBytes_
        : 0U;

    if (fullRange.payloadBytes >
            budgetRemaining &&
        texture.levels.size() > 1U &&
        texture.levels.size() <=
            kMaxStreamedTextureMips) {
        try {
            TextureMipChainDesc desc{};
            desc.id = 1U;
            desc.mipCount =
                static_cast<std::uint32_t>(
                    texture.levels.size());

            for (std::uint32_t mip = 0U;
                 mip < desc.mipCount;
                 ++mip) {
                desc.mipBytes[mip] =
                    texture.levels[mip].
                        byteLength;
            }

            TextureMipResidencyManager planner(
                1U);

            if (planner.registerTexture(
                    desc,
                    0U)) {
                TextureMipChange change{};
                const std::uint64_t target =
                    fullRange.payloadBytes -
                    std::min(
                        fullRange.payloadBytes,
                        budgetRemaining);

                if (planner.planDemotions(
                        target,
                        0U,
                        0U,
                        &change,
                        1U) == 1U) {
                    // Startup quality guard: never discard more than the top
                    // two mips automatically. Runtime streaming can become
                    // more aggressive later if telemetry proves it necessary.
                    residentBaseMip =
                        std::min<std::uint32_t>(
                            change.newBaseMip,
                            std::min<std::uint32_t>(
                                2U,
                                desc.mipCount - 1U));
                }
            }
        } catch (...) {
            residentBaseMip = 0U;
        }
    }

    const auto residentRange =
        planKtx2ResidentMipRange(
            texture,
            residentBaseMip);

    if (!residentRange.valid) {
        return false;
    }

    std::vector<VkDeviceSize> stagingOffsets;
    std::vector<VkBufferImageCopy> regions;

    VkDeviceSize stagingBytes = 0U;

    try {
        stagingOffsets.reserve(
            residentRange.mipCount);
        regions.reserve(
            residentRange.mipCount);

        for (std::size_t sourceMip =
                 residentBaseMip;
             sourceMip < texture.levels.size();
             ++sourceMip) {
            const auto& level =
                texture.levels[sourceMip];

            stagingBytes =
                (stagingBytes + 15U) &
                ~VkDeviceSize{15U};

            stagingOffsets.push_back(
                stagingBytes);

            if (level.byteLength >
                std::numeric_limits<VkDeviceSize>::max() -
                stagingBytes) {
                return false;
            }

            stagingBytes +=
                static_cast<VkDeviceSize>(
                    level.byteLength);
        }
    } catch (...) {
        return false;
    }

    if (stagingBytes == 0U) {
        return false;
    }

    VkBuffer staging = VK_NULL_HANDLE;
    VkDeviceMemory stagingMemory = VK_NULL_HANDLE;

    if (!createBuffer(
            stagingBytes,
            VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
            staging,
            stagingMemory)) {
        return false;
    }

    void* mapped = nullptr;
    if (!ok(
            vkMapMemory(
                device_,
                stagingMemory,
                0U,
                stagingBytes,
                0U,
                &mapped))) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        return false;
    }

    auto* destination =
        static_cast<std::byte*>(mapped);

    for (std::size_t sourceMip =
             residentBaseMip;
         sourceMip < texture.levels.size();
         ++sourceMip) {
        const std::size_t residentMip =
            sourceMip -
            residentBaseMip;
        const auto& level =
            texture.levels[sourceMip];

        std::memcpy(
            destination +
                stagingOffsets[residentMip],
            bytes.data() +
                static_cast<std::size_t>(
                    level.byteOffset),
            static_cast<std::size_t>(
                level.byteLength));

        VkBufferImageCopy copy{};
        copy.bufferOffset =
            stagingOffsets[residentMip];
        copy.bufferRowLength = 0U;
        copy.bufferImageHeight = 0U;
        copy.imageSubresource.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        copy.imageSubresource.mipLevel =
            static_cast<std::uint32_t>(
                residentMip);
        copy.imageSubresource.baseArrayLayer = 0U;
        copy.imageSubresource.layerCount = 1U;
        copy.imageExtent = {
            level.width,
            level.height,
            1U,
        };

        regions.push_back(copy);
    }

    vkUnmapMemory(
        device_,
        stagingMemory);

    VkImageCreateInfo imageInfo{
        VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO
    };
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.extent = {
        residentRange.width,
        residentRange.height,
        1U,
    };
    imageInfo.mipLevels =
        residentRange.mipCount;
    imageInfo.arrayLayers = 1U;
    imageInfo.format = textureFormat;
    imageInfo.tiling =
        VK_IMAGE_TILING_OPTIMAL;
    imageInfo.initialLayout =
        VK_IMAGE_LAYOUT_UNDEFINED;
    imageInfo.usage =
        VK_IMAGE_USAGE_TRANSFER_DST_BIT |
        VK_IMAGE_USAGE_SAMPLED_BIT;
    imageInfo.samples =
        VK_SAMPLE_COUNT_1_BIT;
    imageInfo.sharingMode =
        VK_SHARING_MODE_EXCLUSIVE;

    if (!ok(
            vkCreateImage(
                device_,
                &imageInfo,
                nullptr,
                &out.image))) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        return false;
    }

    VkMemoryRequirements requirements{};
    vkGetImageMemoryRequirements(
        device_,
        out.image,
        &requirements);

    std::uint32_t memoryType = 0U;

    if (!findMemoryType(
            requirements.memoryTypeBits,
            VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
            memoryType)) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        destroyTexture(out);
        return false;
    }

    VkMemoryAllocateInfo allocation{
        VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO
    };
    allocation.allocationSize =
        requirements.size;
    allocation.memoryTypeIndex =
        memoryType;

    if (!ok(
            vkAllocateMemory(
                device_,
                &allocation,
                nullptr,
                &out.memory)) ||
        !ok(
            vkBindImageMemory(
                device_,
                out.image,
                out.memory,
                0U))) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        destroyTexture(out);
        return false;
    }

    VkCommandBuffer command =
        beginUploadCommands();

    if (command == VK_NULL_HANDLE) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        destroyTexture(out);
        return false;
    }

    VkImageMemoryBarrier toTransfer{
        VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
    };
    toTransfer.oldLayout =
        VK_IMAGE_LAYOUT_UNDEFINED;
    toTransfer.newLayout =
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    toTransfer.srcQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toTransfer.dstQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toTransfer.image = out.image;
    toTransfer.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    toTransfer.subresourceRange.baseMipLevel = 0U;
    toTransfer.subresourceRange.levelCount =
        imageInfo.mipLevels;
    toTransfer.subresourceRange.baseArrayLayer = 0U;
    toTransfer.subresourceRange.layerCount = 1U;
    toTransfer.srcAccessMask = 0U;
    toTransfer.dstAccessMask =
        VK_ACCESS_TRANSFER_WRITE_BIT;

    vkCmdPipelineBarrier(
        command,
        VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
        VK_PIPELINE_STAGE_TRANSFER_BIT,
        0U,
        0U, nullptr,
        0U, nullptr,
        1U, &toTransfer);

    vkCmdCopyBufferToImage(
        command,
        staging,
        out.image,
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
        static_cast<std::uint32_t>(
            regions.size()),
        regions.data());

    VkImageMemoryBarrier toShader{
        VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
    };
    toShader.oldLayout =
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    toShader.newLayout =
        VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    toShader.srcQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toShader.dstQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    toShader.image = out.image;
    toShader.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    toShader.subresourceRange.baseMipLevel = 0U;
    toShader.subresourceRange.levelCount =
        imageInfo.mipLevels;
    toShader.subresourceRange.baseArrayLayer = 0U;
    toShader.subresourceRange.layerCount = 1U;
    toShader.srcAccessMask =
        VK_ACCESS_TRANSFER_WRITE_BIT;
    toShader.dstAccessMask =
        VK_ACCESS_SHADER_READ_BIT;

    vkCmdPipelineBarrier(
        command,
        VK_PIPELINE_STAGE_TRANSFER_BIT,
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
        0U,
        0U, nullptr,
        0U, nullptr,
        1U, &toShader);

    if (!queueUploadCommands(
            command,
            staging,
            stagingMemory,
            stagingBytes)) {
        destroyTexture(out);
        return false;
    }

    VkImageViewCreateInfo viewInfo{
        VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
    };
    viewInfo.image = out.image;
    viewInfo.viewType =
        VK_IMAGE_VIEW_TYPE_2D;
    viewInfo.format = textureFormat;
    viewInfo.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.baseMipLevel = 0U;
    viewInfo.subresourceRange.levelCount =
        imageInfo.mipLevels;
    viewInfo.subresourceRange.baseArrayLayer = 0U;
    viewInfo.subresourceRange.layerCount = 1U;

    if (!ok(
            vkCreateImageView(
                device_,
                &viewInfo,
                nullptr,
                &out.view)) ||
        !createTextureSampler(
            imageInfo.mipLevels,
            out)) {
        // The upload has not been submitted yet. Drop the pending batch before
        // invalidating an image referenced by its recorded command buffer.
        discardPendingUploads();
        destroyTexture(out);
        return false;
    }

    out.assetPath = assetPath;
    out.width = texture.width;
    out.height = texture.height;
    out.residentWidth =
        residentRange.width;
    out.residentHeight =
        residentRange.height;
    out.mipLevels =
        residentRange.mipCount;
    out.residentBaseMip =
        residentBaseMip;
    out.sourceMipLevels =
        static_cast<std::uint32_t>(
            std::min<std::size_t>(
                texture.levels.size(),
                kMaxStreamedTextureMips));
    out.sourceMipBytes.fill(0U);

    for (std::uint32_t mip = 0U;
         mip < out.sourceMipLevels;
         ++mip) {
        out.sourceMipBytes[mip] =
            texture.levels[mip].
                byteLength;
    }

    out.residentPayloadBytes =
        residentRange.payloadBytes;
    out.allocationBytes =
        static_cast<std::uint64_t>(
            requirements.size);

    if (residentRange.payloadBytes >
        std::numeric_limits<std::uint64_t>::max() -
            textureResidentBytes_) {
        discardPendingUploads();
        destroyTexture(out);
        return false;
    }

    textureResidentBytes_ +=
        residentRange.payloadBytes;

    if (residentBaseMip > 0U) {
        ++textureDegradedCount_;

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_TEXTURE_MIP_RESIDENCY path=%s base_mip=%u source=%ux%u resident=%ux%u saved_payload_bytes=%llu resident_total_mb=%.2f budget_mb=%.2f degraded=%u",
            assetPath.c_str(),
            static_cast<unsigned int>(
                residentBaseMip),
            texture.width,
            texture.height,
            residentRange.width,
            residentRange.height,
            static_cast<unsigned long long>(
                fullRange.payloadBytes -
                residentRange.payloadBytes),
            static_cast<double>(
                textureResidentBytes_) /
                (1024.0 * 1024.0),
            static_cast<double>(
                textureResidentBudgetBytes_) /
                (1024.0 * 1024.0),
            static_cast<unsigned int>(
                textureDegradedCount_));
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_KTX2_ASTC_TEXTURE path=%s format=%u source=%ux%u resident=%ux%u base_mip=%u mips=%u/%u payload_bytes=%llu gpu_bytes=%llu",
        assetPath.c_str(),
        static_cast<unsigned int>(
            texture.vkFormat),
        texture.width,
        texture.height,
        residentRange.width,
        residentRange.height,
        static_cast<unsigned int>(
            residentBaseMip),
        residentRange.mipCount,
        static_cast<unsigned int>(
            texture.levels.size()),
        static_cast<unsigned long long>(
            residentRange.payloadBytes),
        static_cast<unsigned long long>(
            requirements.size));

    return true;
}

bool VulkanStaticMeshRenderer::createTextureSampler(
    std::uint32_t mipLevels,
    GpuTexture& out,
    float mipLodBias) noexcept {
    if (mipLevels == 0U) {
        return false;
    }

    VkSamplerCreateInfo samplerInfo{
        VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO
    };
    samplerInfo.magFilter = VK_FILTER_LINEAR;
    samplerInfo.minFilter = VK_FILTER_LINEAR;
    samplerInfo.mipmapMode =
        VK_SAMPLER_MIPMAP_MODE_LINEAR;
    samplerInfo.addressModeU =
        VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeV =
        VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeW =
        VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.anisotropyEnable =
        samplerAnisotropyEnabled_
        ? VK_TRUE
        : VK_FALSE;
    samplerInfo.maxAnisotropy =
        maxSamplerAnisotropy_;
    samplerInfo.borderColor =
        VK_BORDER_COLOR_INT_OPAQUE_BLACK;
    samplerInfo.unnormalizedCoordinates =
        VK_FALSE;
    // Sanctum's original photogrammetry textures top out at 1024 px.
    // A small negative bias preserves authored edge/detail energy when the
    // scene is rendered below native scale, while anisotropy keeps oblique
    // surfaces stable.  Keep this conservative to avoid mobile shimmer.
    samplerInfo.mipLodBias =
        mipLevels > 1U
        ? mipLodBias
        : 0.0f;
    samplerInfo.minLod = 0.0f;
    samplerInfo.maxLod =
        static_cast<float>(
            mipLevels - 1U);

    return ok(
        vkCreateSampler(
            device_,
            &samplerInfo,
            nullptr,
            &out.sampler));
}

bool VulkanStaticMeshRenderer::createPngTexture(
    AAssetManager* assetManager,
    const std::string& assetPath,
    bool srgb,
    GpuTexture& out) noexcept {
    AAsset* asset =
        AAssetManager_open(
            assetManager,
            assetPath.c_str(),
            AASSET_MODE_STREAMING);

    if (asset == nullptr) {
        return false;
    }

    AImageDecoder* decoder = nullptr;
    const int createResult =
        AImageDecoder_createFromAAsset(
            asset,
            &decoder);

    if (createResult != ANDROID_IMAGE_DECODER_SUCCESS ||
        decoder == nullptr) {
        AAsset_close(asset);
        return false;
    }

    (void) AImageDecoder_setAndroidBitmapFormat(
        decoder,
        ANDROID_BITMAP_FORMAT_RGBA_8888);

    const AImageDecoderHeaderInfo* header =
        AImageDecoder_getHeaderInfo(decoder);

    const int32_t width =
        AImageDecoderHeaderInfo_getWidth(header);
    const int32_t height =
        AImageDecoderHeaderInfo_getHeight(header);
    const std::size_t stride =
        AImageDecoder_getMinimumStride(decoder);

    if (width <= 0 ||
        height <= 0 ||
        stride < static_cast<std::size_t>(width) * 4U) {
        AImageDecoder_delete(decoder);
        AAsset_close(asset);
        return false;
    }

    const std::size_t pixelBytes =
        stride * static_cast<std::size_t>(height);

    std::vector<std::byte> pixels;
    try {
        pixels.resize(pixelBytes);
    } catch (...) {
        AImageDecoder_delete(decoder);
        AAsset_close(asset);
        return false;
    }

    const int decodeResult =
        AImageDecoder_decodeImage(
            decoder,
            pixels.data(),
            stride,
            pixels.size());

    AImageDecoder_delete(decoder);
    AAsset_close(asset);

    if (decodeResult != ANDROID_IMAGE_DECODER_SUCCESS) {
        return false;
    }

    const VkFormat textureFormat =
        srgb
        ? VK_FORMAT_R8G8B8A8_SRGB
        : VK_FORMAT_R8G8B8A8_UNORM;

    VkFormatProperties formatProperties{};
    vkGetPhysicalDeviceFormatProperties(
        physicalDevice_,
        textureFormat,
        &formatProperties);

    const bool linearBlitSupported =
        (formatProperties.optimalTilingFeatures &
         VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT) != 0U;

    const std::uint32_t maxDimension =
        static_cast<std::uint32_t>(
            std::max(width, height));

    const std::uint32_t mipLevels =
        linearBlitSupported
        ? 1U +
              static_cast<std::uint32_t>(
                  std::floor(
                      std::log2(
                          static_cast<double>(
                              std::max(maxDimension, 1U)))))
        : 1U;

    VkBuffer staging = VK_NULL_HANDLE;
    VkDeviceMemory stagingMemory =
        VK_NULL_HANDLE;

    if (!createBuffer(
            pixelBytes,
            VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
            staging,
            stagingMemory)) {
        return false;
    }

    void* mapped = nullptr;
    if (!ok(
            vkMapMemory(
                device_,
                stagingMemory,
                0U,
                pixelBytes,
                0U,
                &mapped))) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        return false;
    }

    std::memcpy(
        mapped,
        pixels.data(),
        pixelBytes);
    vkUnmapMemory(
        device_,
        stagingMemory);

    VkImageCreateInfo imageInfo{
        VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO
    };
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.extent.width =
        static_cast<std::uint32_t>(width);
    imageInfo.extent.height =
        static_cast<std::uint32_t>(height);
    imageInfo.extent.depth = 1U;
    imageInfo.mipLevels = mipLevels;
    imageInfo.arrayLayers = 1U;
    imageInfo.format = textureFormat;
    imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
    imageInfo.initialLayout =
        VK_IMAGE_LAYOUT_UNDEFINED;
    imageInfo.usage =
        VK_IMAGE_USAGE_TRANSFER_DST_BIT |
        VK_IMAGE_USAGE_SAMPLED_BIT |
        (mipLevels > 1U
            ? VK_IMAGE_USAGE_TRANSFER_SRC_BIT
            : 0U);
    imageInfo.samples =
        VK_SAMPLE_COUNT_1_BIT;
    imageInfo.sharingMode =
        VK_SHARING_MODE_EXCLUSIVE;

    if (!ok(
            vkCreateImage(
                device_,
                &imageInfo,
                nullptr,
                &out.image))) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        return false;
    }

    VkMemoryRequirements requirements{};
    vkGetImageMemoryRequirements(
        device_,
        out.image,
        &requirements);

    std::uint32_t memoryType = 0U;
    if (!findMemoryType(
            requirements.memoryTypeBits,
            VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
            memoryType)) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        destroyTexture(out);
        return false;
    }

    VkMemoryAllocateInfo allocation{
        VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO
    };
    allocation.allocationSize = requirements.size;
    allocation.memoryTypeIndex = memoryType;

    if (!ok(
            vkAllocateMemory(
                device_,
                &allocation,
                nullptr,
                &out.memory)) ||
        !ok(
            vkBindImageMemory(
                device_,
                out.image,
                out.memory,
                0U))) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        destroyTexture(out);
        return false;
    }

    VkCommandBuffer command =
        beginUploadCommands();

    if (command == VK_NULL_HANDLE) {
        vkFreeMemory(
            device_, stagingMemory, nullptr);
        vkDestroyBuffer(
            device_, staging, nullptr);
        destroyTexture(out);
        return false;
    }

    VkImageMemoryBarrier initialBarrier{
        VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
    };
    initialBarrier.oldLayout =
        VK_IMAGE_LAYOUT_UNDEFINED;
    initialBarrier.newLayout =
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    initialBarrier.srcQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    initialBarrier.dstQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    initialBarrier.image = out.image;
    initialBarrier.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    initialBarrier.subresourceRange.baseMipLevel = 0U;
    initialBarrier.subresourceRange.levelCount =
        mipLevels;
    initialBarrier.subresourceRange.baseArrayLayer = 0U;
    initialBarrier.subresourceRange.layerCount = 1U;
    initialBarrier.srcAccessMask = 0U;
    initialBarrier.dstAccessMask =
        VK_ACCESS_TRANSFER_WRITE_BIT;

    vkCmdPipelineBarrier(
        command,
        VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
        VK_PIPELINE_STAGE_TRANSFER_BIT,
        0U,
        0U, nullptr,
        0U, nullptr,
        1U, &initialBarrier);

    VkBufferImageCopy copy{};
    copy.bufferOffset = 0U;
    copy.bufferRowLength =
        static_cast<std::uint32_t>(
            stride / 4U);
    copy.bufferImageHeight =
        static_cast<std::uint32_t>(height);
    copy.imageSubresource.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    copy.imageSubresource.mipLevel = 0U;
    copy.imageSubresource.baseArrayLayer = 0U;
    copy.imageSubresource.layerCount = 1U;
    copy.imageExtent = {
        static_cast<std::uint32_t>(width),
        static_cast<std::uint32_t>(height),
        1U,
    };

    vkCmdCopyBufferToImage(
        command,
        staging,
        out.image,
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
        1U,
        &copy);

    std::int32_t mipWidth = width;
    std::int32_t mipHeight = height;

    for (std::uint32_t level = 1U;
         level < mipLevels;
         ++level) {
        VkImageMemoryBarrier previousToSource{
            VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
        };
        previousToSource.oldLayout =
            VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        previousToSource.newLayout =
            VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        previousToSource.srcQueueFamilyIndex =
            VK_QUEUE_FAMILY_IGNORED;
        previousToSource.dstQueueFamilyIndex =
            VK_QUEUE_FAMILY_IGNORED;
        previousToSource.image = out.image;
        previousToSource.subresourceRange.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        previousToSource.subresourceRange.baseMipLevel =
            level - 1U;
        previousToSource.subresourceRange.levelCount = 1U;
        previousToSource.subresourceRange.baseArrayLayer = 0U;
        previousToSource.subresourceRange.layerCount = 1U;
        previousToSource.srcAccessMask =
            VK_ACCESS_TRANSFER_WRITE_BIT;
        previousToSource.dstAccessMask =
            VK_ACCESS_TRANSFER_READ_BIT;

        vkCmdPipelineBarrier(
            command,
            VK_PIPELINE_STAGE_TRANSFER_BIT,
            VK_PIPELINE_STAGE_TRANSFER_BIT,
            0U,
            0U, nullptr,
            0U, nullptr,
            1U, &previousToSource);

        const std::int32_t nextWidth =
            std::max(mipWidth / 2, 1);
        const std::int32_t nextHeight =
            std::max(mipHeight / 2, 1);

        VkImageBlit blit{};
        blit.srcOffsets[0] = {0, 0, 0};
        blit.srcOffsets[1] = {
            mipWidth,
            mipHeight,
            1,
        };
        blit.srcSubresource.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        blit.srcSubresource.mipLevel =
            level - 1U;
        blit.srcSubresource.baseArrayLayer = 0U;
        blit.srcSubresource.layerCount = 1U;
        blit.dstOffsets[0] = {0, 0, 0};
        blit.dstOffsets[1] = {
            nextWidth,
            nextHeight,
            1,
        };
        blit.dstSubresource.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        blit.dstSubresource.mipLevel = level;
        blit.dstSubresource.baseArrayLayer = 0U;
        blit.dstSubresource.layerCount = 1U;

        vkCmdBlitImage(
            command,
            out.image,
            VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
            out.image,
            VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
            1U,
            &blit,
            VK_FILTER_LINEAR);

        VkImageMemoryBarrier previousToShader{
            VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
        };
        previousToShader.oldLayout =
            VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        previousToShader.newLayout =
            VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        previousToShader.srcQueueFamilyIndex =
            VK_QUEUE_FAMILY_IGNORED;
        previousToShader.dstQueueFamilyIndex =
            VK_QUEUE_FAMILY_IGNORED;
        previousToShader.image = out.image;
        previousToShader.subresourceRange.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        previousToShader.subresourceRange.baseMipLevel =
            level - 1U;
        previousToShader.subresourceRange.levelCount = 1U;
        previousToShader.subresourceRange.baseArrayLayer = 0U;
        previousToShader.subresourceRange.layerCount = 1U;
        previousToShader.srcAccessMask =
            VK_ACCESS_TRANSFER_READ_BIT;
        previousToShader.dstAccessMask =
            VK_ACCESS_SHADER_READ_BIT;

        vkCmdPipelineBarrier(
            command,
            VK_PIPELINE_STAGE_TRANSFER_BIT,
            VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
            0U,
            0U, nullptr,
            0U, nullptr,
            1U, &previousToShader);

        mipWidth = nextWidth;
        mipHeight = nextHeight;
    }

    VkImageMemoryBarrier finalToShader{
        VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER
    };
    finalToShader.oldLayout =
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    finalToShader.newLayout =
        VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    finalToShader.srcQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    finalToShader.dstQueueFamilyIndex =
        VK_QUEUE_FAMILY_IGNORED;
    finalToShader.image = out.image;
    finalToShader.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    finalToShader.subresourceRange.baseMipLevel =
        mipLevels - 1U;
    finalToShader.subresourceRange.levelCount = 1U;
    finalToShader.subresourceRange.baseArrayLayer = 0U;
    finalToShader.subresourceRange.layerCount = 1U;
    finalToShader.srcAccessMask =
        VK_ACCESS_TRANSFER_WRITE_BIT;
    finalToShader.dstAccessMask =
        VK_ACCESS_SHADER_READ_BIT;

    vkCmdPipelineBarrier(
        command,
        VK_PIPELINE_STAGE_TRANSFER_BIT,
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
        0U,
        0U, nullptr,
        0U, nullptr,
        1U, &finalToShader);

    if (!queueUploadCommands(
            command,
            staging,
            stagingMemory,
            pixelBytes)) {
        destroyTexture(out);
        return false;
    }

    VkImageViewCreateInfo viewInfo{
        VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
    };
    viewInfo.image = out.image;
    viewInfo.viewType =
        VK_IMAGE_VIEW_TYPE_2D;
    viewInfo.format = textureFormat;
    viewInfo.subresourceRange.aspectMask =
        VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.baseMipLevel = 0U;
    viewInfo.subresourceRange.levelCount =
        mipLevels;
    viewInfo.subresourceRange.baseArrayLayer = 0U;
    viewInfo.subresourceRange.layerCount = 1U;

    if (!ok(
            vkCreateImageView(
                device_,
                &viewInfo,
                nullptr,
                &out.view))) {
        discardPendingUploads();
        destroyTexture(out);
        return false;
    }

    const bool closeStGilesExterior =
        srgb &&
        assetPath.find(
            "StGilesCripplegateExterior04") !=
            std::string::npos;

    if (closeStGilesExterior) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_ST_GILES_CLOSE_DETAIL_SAMPLER_V1 size=%dx%d lod_bias=-0.90",
            width,
            height);
    }

    if (!createTextureSampler(
            mipLevels,
            out,
            closeStGilesExterior
                ? -0.90f
                : -0.35f)) {
        discardPendingUploads();
        destroyTexture(out);
        return false;
    }

    out.assetPath = assetPath;
    out.width =
        static_cast<std::uint32_t>(width);
    out.height =
        static_cast<std::uint32_t>(height);
    out.residentWidth = out.width;
    out.residentHeight = out.height;
    out.mipLevels = mipLevels;
    out.residentBaseMip = 0U;
    out.sourceMipLevels =
        std::min<std::uint32_t>(
            mipLevels,
            static_cast<std::uint32_t>(
                kMaxStreamedTextureMips));
    out.sourceMipBytes.fill(0U);

    std::uint32_t registryMipWidth =
        out.width;
    std::uint32_t registryMipHeight =
        out.height;

    for (std::uint32_t mip = 0U;
         mip < out.sourceMipLevels;
         ++mip) {
        out.sourceMipBytes[mip] =
            std::max<std::uint64_t>(
                1U,
                static_cast<std::uint64_t>(
                    registryMipWidth) *
                static_cast<std::uint64_t>(
                    registryMipHeight) *
                4U);

        registryMipWidth =
            std::max<std::uint32_t>(
                1U,
                registryMipWidth / 2U);
        registryMipHeight =
            std::max<std::uint32_t>(
                1U,
                registryMipHeight / 2U);
    }

    out.residentPayloadBytes =
        static_cast<std::uint64_t>(
            pixelBytes);
    out.allocationBytes =
        static_cast<std::uint64_t>(
            requirements.size);

    return true;
}

bool VulkanStaticMeshRenderer::createMaterialDescriptor(
    GpuMaterial& material) noexcept {
    if (descriptorPool_ == VK_NULL_HANDLE ||
        descriptorSetLayout_ == VK_NULL_HANDLE ||
        material.albedoTextureIndex >= textures_.size() ||
        material.normalTextureIndex >= textures_.size() ||
        material.ormTextureIndex >= textures_.size() ||
        material.emissiveTextureIndex >= textures_.size()) {
        return false;
    }

    std::array<VkDescriptorSetLayout, kDescriptorFrames>
        layouts{};
    layouts.fill(
        descriptorSetLayout_);

    VkDescriptorSetAllocateInfo allocation{
        VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO
    };
    allocation.descriptorPool = descriptorPool_;
    allocation.descriptorSetCount =
        kDescriptorFrames;
    allocation.pSetLayouts =
        layouts.data();

    material.descriptorSets.fill(
        VK_NULL_HANDLE);

    if (!ok(
            vkAllocateDescriptorSets(
                device_,
                &allocation,
                material.descriptorSets.data()))) {
        material.descriptorSets.fill(
            VK_NULL_HANDLE);
        return false;
    }

    const std::array<std::uint32_t, 4> indices{{
        material.albedoTextureIndex,
        material.normalTextureIndex,
        material.ormTextureIndex,
        material.emissiveTextureIndex,
    }};

    std::array<VkDescriptorImageInfo, 4> images{};

    for (std::uint32_t binding = 0U;
         binding < indices.size();
         ++binding) {
        const auto& texture =
            textures_[indices[binding]];

        images[binding].sampler =
            texture.sampler;
        images[binding].imageView =
            texture.view;
        images[binding].imageLayout =
            VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    }

    for (std::uint32_t frame = 0U;
         frame < kDescriptorFrames;
         ++frame) {
        std::array<VkWriteDescriptorSet, 4>
            writes{};

        for (std::uint32_t binding = 0U;
             binding < indices.size();
             ++binding) {
            writes[binding] = {
                VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET
            };
            writes[binding].dstSet =
                material.descriptorSets[frame];
            writes[binding].dstBinding =
                binding;
            writes[binding].descriptorCount =
                1U;
            writes[binding].descriptorType =
                VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
            writes[binding].pImageInfo =
                &images[binding];
        }

        vkUpdateDescriptorSets(
            device_,
            static_cast<std::uint32_t>(
                writes.size()),
            writes.data(),
            0U,
            nullptr);
    }

    return true;
}

bool VulkanStaticMeshRenderer::createShaderModule(
    AAssetManager* assetManager,
    const char* path,
    VkShaderModule& out) noexcept {
    out = VK_NULL_HANDLE;

    AAsset* asset =
        AAssetManager_open(
            assetManager,
            path,
            AASSET_MODE_BUFFER);

    if (asset == nullptr) {
        return false;
    }

    const off_t length =
        AAsset_getLength(asset);

    if (length <= 0 ||
        (length % 4) != 0) {
        AAsset_close(asset);
        return false;
    }

    std::vector<std::uint32_t> words;

    try {
        words.resize(
            static_cast<std::size_t>(
                length) / 4U);
    } catch (...) {
        AAsset_close(asset);
        return false;
    }

    const int read =
        AAsset_read(
            asset,
            words.data(),
            static_cast<std::size_t>(
                length));

    AAsset_close(asset);

    if (read < 0 ||
        static_cast<off_t>(read) !=
            length) {
        return false;
    }

    VkShaderModuleCreateInfo info{
        VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO
    };
    info.codeSize =
        static_cast<std::size_t>(
            length);
    info.pCode =
        words.data();

    return ok(
        vkCreateShaderModule(
            device_,
            &info,
            nullptr,
            &out));
}

bool VulkanStaticMeshRenderer::findMemoryType(
    std::uint32_t typeBits,
    VkMemoryPropertyFlags required,
    std::uint32_t& outIndex) const noexcept {
    VkPhysicalDeviceMemoryProperties properties{};
    vkGetPhysicalDeviceMemoryProperties(
        physicalDevice_,
        &properties);

    for (std::uint32_t i = 0U;
         i < properties.memoryTypeCount;
         ++i) {
        if ((typeBits & (1U << i)) != 0U &&
            (properties.memoryTypes[i].
                 propertyFlags &
             required) == required) {
            outIndex = i;
            return true;
        }
    }

    return false;
}

VkCommandBuffer
VulkanStaticMeshRenderer::beginUploadCommands() noexcept {
    VkCommandBufferAllocateInfo allocation{
        VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO
    };
    allocation.commandPool =
        commandPool_;
    allocation.level =
        VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    allocation.commandBufferCount = 1U;

    VkCommandBuffer command =
        VK_NULL_HANDLE;

    if (!ok(
            vkAllocateCommandBuffers(
                device_,
                &allocation,
                &command))) {
        return VK_NULL_HANDLE;
    }

    VkCommandBufferBeginInfo begin{
        VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO
    };
    begin.flags =
        VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;

    if (!ok(
            vkBeginCommandBuffer(
                command,
                &begin))) {
        vkFreeCommandBuffers(
            device_,
            commandPool_,
            1U,
            &command);
        return VK_NULL_HANDLE;
    }

    return command;
}

bool VulkanStaticMeshRenderer::queueUploadCommands(
    VkCommandBuffer command,
    VkBuffer stagingBuffer,
    VkDeviceMemory stagingMemory,
    VkDeviceSize stagingBytes) noexcept {
    constexpr VkDeviceSize kSoftBatchLimit =
        96ULL * 1024ULL * 1024ULL;

    const auto releaseCurrent =
        [&]() noexcept {
            if (command != VK_NULL_HANDLE) {
                vkFreeCommandBuffers(
                    device_,
                    commandPool_,
                    1U,
                    &command);
            }
            if (stagingBuffer != VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    stagingBuffer,
                    nullptr);
            }
            if (stagingMemory != VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    stagingMemory,
                    nullptr);
            }
        };

    if (command == VK_NULL_HANDLE ||
        stagingBuffer == VK_NULL_HANDLE ||
        stagingMemory == VK_NULL_HANDLE ||
        stagingBytes == 0U) {
        releaseCurrent();
        return false;
    }

    if (!pendingUploads_.empty() &&
        (pendingUploads_.size() >=
             std::max<std::uint32_t>(
                 uploadBatchCommandLimit_,
                 1U) ||
         pendingUploadBytes_ >
             kSoftBatchLimit ||
         stagingBytes >
             kSoftBatchLimit -
                 std::min(
                     pendingUploadBytes_,
                     kSoftBatchLimit))) {
        if (!flushPendingUploads()) {
            releaseCurrent();
            return false;
        }
    }

    if (!ok(
            vkEndCommandBuffer(
                command))) {
        releaseCurrent();
        return false;
    }

    try {
        pendingUploads_.push_back({
            .command = command,
            .stagingBuffer = stagingBuffer,
            .stagingMemory = stagingMemory,
            .stagingBytes = stagingBytes,
        });
    } catch (...) {
        releaseCurrent();
        return false;
    }

    if (stagingBytes >
        std::numeric_limits<VkDeviceSize>::max() -
            pendingUploadBytes_) {
        // The command is owned by the pending list now; discard all rather
        // than leaving a partially-accounted batch.
        discardPendingUploads();
        return false;
    }

    pendingUploadBytes_ +=
        stagingBytes;

    return true;
}

bool VulkanStaticMeshRenderer::flushPendingUploads() noexcept {
    if (pendingUploads_.empty()) {
        pendingUploadBytes_ = 0U;
        return true;
    }

    std::vector<VkCommandBuffer> commands;

    try {
        commands.reserve(
            pendingUploads_.size());

        for (const auto& upload :
             pendingUploads_) {
            commands.push_back(
                upload.command);
        }
    } catch (...) {
        discardPendingUploads();
        return false;
    }

    VkSubmitInfo submit{
        VK_STRUCTURE_TYPE_SUBMIT_INFO
    };
    submit.commandBufferCount =
        static_cast<std::uint32_t>(
            commands.size());
    submit.pCommandBuffers =
        commands.data();

    const VkResult submitResult =
        vkQueueSubmit(
            graphicsQueue_,
            1U,
            &submit,
            VK_NULL_HANDLE);

    VkResult waitResult =
        submitResult;

    if (ok(submitResult)) {
        waitResult =
            vkQueueWaitIdle(
                graphicsQueue_);

        if (!ok(waitResult)) {
            // Initialization is still single-threaded here. Make one best
            // effort device wait before tearing down resources referenced by
            // a failed queue wait.
            (void) vkDeviceWaitIdle(
                device_);
        }
    }

    const std::size_t commandCount =
        pendingUploads_.size();
    const VkDeviceSize batchBytes =
        pendingUploadBytes_;

    for (auto& upload : pendingUploads_) {
        if (upload.command != VK_NULL_HANDLE) {
            vkFreeCommandBuffers(
                device_,
                commandPool_,
                1U,
                &upload.command);
        }
        if (upload.stagingBuffer != VK_NULL_HANDLE) {
            vkDestroyBuffer(
                device_,
                upload.stagingBuffer,
                nullptr);
        }
        if (upload.stagingMemory != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                upload.stagingMemory,
                nullptr);
        }
    }

    pendingUploads_.clear();
    pendingUploadBytes_ = 0U;

    if (!ok(submitResult) ||
        !ok(waitResult)) {
        return false;
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_TEXTURE_UPLOAD_BATCH commands=%u limit=%u staging_mb=%.2f",
        static_cast<unsigned int>(
            commandCount),
        static_cast<unsigned int>(
            uploadBatchCommandLimit_),
        static_cast<double>(
            batchBytes) /
            (1024.0 * 1024.0));

    return true;
}

void VulkanStaticMeshRenderer::discardPendingUploads() noexcept {
    if (device_ == VK_NULL_HANDLE) {
        pendingUploads_.clear();
        pendingUploadBytes_ = 0U;
        return;
    }

    for (auto& upload : pendingUploads_) {
        if (upload.command != VK_NULL_HANDLE) {
            vkFreeCommandBuffers(
                device_,
                commandPool_,
                1U,
                &upload.command);
        }
        if (upload.stagingBuffer != VK_NULL_HANDLE) {
            vkDestroyBuffer(
                device_,
                upload.stagingBuffer,
                nullptr);
        }
        if (upload.stagingMemory != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                upload.stagingMemory,
                nullptr);
        }
    }

    pendingUploads_.clear();
    pendingUploadBytes_ = 0U;
}

void VulkanStaticMeshRenderer::destroyTexture(
    GpuTexture& texture) noexcept {
    if (device_ == VK_NULL_HANDLE) {
        texture = {};
        return;
    }

    if (texture.sampler != VK_NULL_HANDLE) {
        vkDestroySampler(
            device_,
            texture.sampler,
            nullptr);
    }

    if (texture.view != VK_NULL_HANDLE) {
        vkDestroyImageView(
            device_,
            texture.view,
            nullptr);
    }

    if (texture.image != VK_NULL_HANDLE) {
        vkDestroyImage(
            device_,
            texture.image,
            nullptr);
    }

    if (texture.memory != VK_NULL_HANDLE) {
        vkFreeMemory(
            device_,
            texture.memory,
            nullptr);
    }

    texture = {};
}

bool VulkanStaticMeshRenderer::createIndirectDrawBuffers() noexcept {
    destroyIndirectDrawBuffers();

    try {
        visibleDrawCandidates_.reserve(
            batches_.size());
        drawCommands_.reserve(
            batches_.size());
        drawGroups_.reserve(
            batches_.size());
    } catch (...) {
        return false;
    }

    if (!multiDrawIndirectEnabled_ ||
        batches_.empty()) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_STATIC_DRAW_SUBMISSION_READY mode=direct max_draws=%u",
            static_cast<unsigned int>(
                batches_.size()));
        return true;
    }

    if (batches_.size() >
        std::numeric_limits<VkDeviceSize>::max() /
            sizeof(VkDrawIndexedIndirectCommand)) {
        multiDrawIndirectEnabled_ = false;
        return true;
    }

    const VkDeviceSize bytes =
        static_cast<VkDeviceSize>(
            batches_.size()) *
        sizeof(VkDrawIndexedIndirectCommand);

    const VkMemoryPropertyFlags memoryFlags =
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
        VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;

    for (auto& frame : indirectDrawFrames_) {
        if (!createBuffer(
                bytes,
                VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT,
                memoryFlags,
                frame.buffer,
                frame.memory) ||
            !ok(
                vkMapMemory(
                    device_,
                    frame.memory,
                    0U,
                    bytes,
                    0U,
                    &frame.mapped))) {
            destroyIndirectDrawBuffers();
            multiDrawIndirectEnabled_ = false;

            __android_log_print(
                ANDROID_LOG_WARN,
                kTag,
                "XZIEL_STATIC_DRAW_SUBMISSION_FALLBACK reason=indirect_buffer_allocation");

            return true;
        }

        frame.bytes = bytes;
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_STATIC_DRAW_SUBMISSION_READY mode=multi_draw_indirect frames=%u max_draws=%u bytes_per_frame=%llu",
        static_cast<unsigned int>(
            kDescriptorFrames),
        static_cast<unsigned int>(
            batches_.size()),
        static_cast<unsigned long long>(
            bytes));

    return true;
}

void VulkanStaticMeshRenderer::destroyIndirectDrawBuffers() noexcept {
    if (device_ != VK_NULL_HANDLE) {
        for (auto& frame : indirectDrawFrames_) {
            if (frame.mapped != nullptr &&
                frame.memory != VK_NULL_HANDLE) {
                vkUnmapMemory(
                    device_,
                    frame.memory);
            }

            if (frame.buffer != VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    frame.buffer,
                    nullptr);
            }

            if (frame.memory != VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    frame.memory,
                    nullptr);
            }

            frame = {};
        }
    } else {
        indirectDrawFrames_ = {};
    }

    visibleDrawCandidates_.clear();
    visibleDrawCandidates_.shrink_to_fit();
    drawCommands_.clear();
    drawGroups_.clear();
}

void VulkanStaticMeshRenderer::destroyGeometryResidency() noexcept {
    destroyIndirectDrawBuffers();
    batches_.clear();

    if (device_ != VK_NULL_HANDLE) {
        for (std::size_t i = 0U;
             i < geometryCellCount_;
             ++i) {
            auto& cell =
                geometryCells_[i];

            if (cell.restoreMappedIndices != nullptr &&
                cell.indexMemory != VK_NULL_HANDLE) {
                vkUnmapMemory(
                    device_,
                    cell.indexMemory);
                cell.restoreMappedIndices = nullptr;
            }

            if (cell.restoreMappedVertices != nullptr &&
                cell.vertexMemory != VK_NULL_HANDLE) {
                vkUnmapMemory(
                    device_,
                    cell.vertexMemory);
                cell.restoreMappedVertices = nullptr;
            }

            if (cell.indexBuffer !=
                VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    cell.indexBuffer,
                    nullptr);
            }

            if (cell.indexMemory !=
                VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    cell.indexMemory,
                    nullptr);
            }

            if (cell.vertexBuffer !=
                VK_NULL_HANDLE) {
                vkDestroyBuffer(
                    device_,
                    cell.vertexBuffer,
                    nullptr);
            }

            if (cell.vertexMemory !=
                VK_NULL_HANDLE) {
                vkFreeMemory(
                    device_,
                    cell.vertexMemory,
                    nullptr);
            }
        }

        if (geometryIndexBuffer_ != VK_NULL_HANDLE) {
            vkDestroyBuffer(
                device_,
                geometryIndexBuffer_,
                nullptr);
        }

        if (geometryIndexMemory_ != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                geometryIndexMemory_,
                nullptr);
        }

        if (geometryVertexBuffer_ != VK_NULL_HANDLE) {
            vkDestroyBuffer(
                device_,
                geometryVertexBuffer_,
                nullptr);
        }

        if (geometryVertexMemory_ != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                geometryVertexMemory_,
                nullptr);
        }
    }

    geometryCells_ = {};
    geometryCellCount_ = 0U;
    geometryCellVertexBytes_ = 0U;
    geometryCellIndexBytes_ = 0U;
    geometryResidentBytes_ = 0U;
    geometryReloadCellSlot_ = UINT32_MAX;

    geometryVertexBuffer_ =
        VK_NULL_HANDLE;
    geometryVertexMemory_ =
        VK_NULL_HANDLE;
    geometryIndexBuffer_ =
        VK_NULL_HANDLE;
    geometryIndexMemory_ =
        VK_NULL_HANDLE;
    geometryDeviceLocalHostVisible_ = false;
    geometryVertexBytes_ = 0U;
    geometryIndexBytes_ = 0U;
}

} // namespace xziel::android
