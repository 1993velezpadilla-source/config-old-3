#pragma once

#include <android/asset_manager.h>
#include <android/native_window.h>
#include <jni.h>
#include <vulkan/vulkan.h>

#include "vulkan_static_mesh_renderer.hpp"
#include "xziel/weapon_catalog.hpp"

#include <array>
#include <cstdint>
#include <vector>

namespace xziel::android {

struct VulkanCamera {
    float x = 0.0f;
    float y = 0.14f;
    float z = -2.55f;

    float yawRadians = 0.0f;
    float pitchRadians = 0.0f;
    float verticalFovDegrees = 72.0f;
};

struct VulkanMapBoxState {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;

    float scaleX = 1.0f;
    float scaleY = 1.0f;
    float scaleZ = 1.0f;

    float materialId = 0.0f;
    bool visible = false;
};

struct VulkanDoorState {
    std::uint32_t id = 0;
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    float halfX = 0.08f;
    float halfY = 1.0f;
    float halfZ = 0.55f;
    float openProgress = 0.0f;
    bool visible = false;
};

struct VulkanWindowState {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;

    float halfWidth = 0.5f;
    float halfHeight = 1.0f;
    float halfDepth = 0.08f;

    std::uint32_t intactPlanks = 0;
    std::uint32_t maximumPlanks = 0;
    bool visible = false;
};

struct VulkanZombieState {
    float x = 0.0f;
    float y = -1.48f;
    float z = 2.45f;

    float yawRadians = 0.0f;
    float stridePhase = 0.0f;
    float healthRatio = 1.0f;

    bool visible = false;
    bool staggered = false;
    bool attack = false;
};

struct VulkanSceneState {
    std::array<VulkanMapBoxState, 128> mapBoxes{};
    std::size_t mapBoxCount = 0;

    std::array<VulkanDoorState, 16> doors{};
    std::size_t doorCount = 0;

    std::array<VulkanWindowState, 32> windows{};
    std::size_t windowCount = 0;

    std::array<VulkanZombieState, 8> zombies{};
    std::size_t zombieCount = 0;

    float roundProgress = 0.0f;
    bool interRound = false;

    float impactX = 0.0f;
    float impactY = 0.0f;
    float impactZ = 0.0f;
    float impactAlpha = 0.0f;
    bool impactCritical = false;

    float decapOriginX = 0.0f;
    float decapOriginY = 0.0f;
    float decapOriginZ = 0.0f;

    float decapDirectionX = 0.0f;
    float decapDirectionY = 0.0f;
    float decapDirectionZ = 1.0f;

    float decapAlpha = 0.0f;

    float interactionX = 0.0f;
    float interactionY = 0.0f;
    float interactionZ = 0.0f;

    bool interactionVisible = false;
    bool interactionActive = false;

    float doorOpenAlpha = 0.0f;
};

struct VulkanEnvironmentState {
    float rainIntensity = 0.0f;
    float fogDensity = 0.0f;
    float lightningFlash = 0.0f;
    float wetness = 0.0f;

    float windX = 0.0f;
    float windZ = 0.0f;

    // World rendering can scale independently of the native-resolution HUD.
    // PerformanceGovernor owns the policy; the Vulkan backend only consumes it.
    float renderScale = 1.0f;
    float particleDensityScale = 1.0f;
    float fogQualityScale = 1.0f;
    float postProcessScale = 1.0f;

    MemoryPressure memoryPressure =
        MemoryPressure::Normal;

    float waterWavePhase = 0.0f;
    float waterFoamStrength = 0.0f;
    float waterReflectionStrength = 0.0f;
    float waterRefractionStrength = 0.0f;
    float waterRoughness = 0.10f;

    // Explicit reflection workload controls carried from PerformanceGovernor
    // into the Vulkan backend. The renderer can now decide whether an
    // offscreen planar pass is legal without guessing from visual quality.
    std::uint32_t maxPlanarReflectionPasses = 0;
    float planarReflectionScale = 0.0f;
    float reflectionDistanceMeters = 0.0f;
    bool ssrEnabled = false;
    float ssrResolutionScale = 0.0f;
    std::uint32_t ssrMaxSteps = 0;
    std::uint32_t planarReflectionUpdateEveryNFrames = 1;
    bool planarReflectionVisible = true;
    float planarReflectionScreenCoverage = 1.0f;

    // Selected planar surface geometry in normalized world-space form.
    // n.x*x + n.y*y + n.z*z + d = 0. This is carried explicitly so the
    // backend no longer has to invent the capture plane.
    float planarPlaneNormalX = 0.0f;
    float planarPlaneNormalY = 1.0f;
    float planarPlaneNormalZ = 0.0f;
    float planarPlaneDistance = 1.48f;

    // Material that currently owns the single live planar target. The main
    // shader samples the target only for this material to prevent water from
    // sampling a mirror capture (and vice versa).
    std::uint32_t planarReflectionMaterialId = 0;
};

struct VulkanHudState {
    float moveX = 0.0f;
    float moveY = 0.0f;

    float moveAnchorX = 0.17f;
    float moveAnchorY = 0.74f;

    bool moveActive = false;
    bool fire = false;
    bool aim = false;
    bool reload = false;
    bool jump = false;
    bool stance = false;
    bool gyroAvailable = false;

    bool interactAvailable = false;
    bool interactHeld = false;
    float interactProgress = 0.0f;

    std::uint32_t interactionCost = 0;
    bool interactionAffordable = true;
    float interactionDeniedAlpha = 0.0f;

    float hitMarkerAlpha = 0.0f;
    float criticalHitAlpha = 0.0f;
    bool targetAlive = true;

    float weaponAdsAlpha = 0.0f;
    float weaponReloadAlpha = 0.0f;
    float weaponFireAlpha = 0.0f;
    float weaponMagazineRatio = 1.0f;
    float viewmodelLowering = 0.0f;
    xziel::WeaponViewmodelProfile weaponViewmodel{};

    float playerHealthRatio = 1.0f;
    float damageFlashAlpha = 0.0f;
    float deathAlpha = 0.0f;
    float horrorVignette = 0.0f;
    bool restartVisible = false;

    std::uint64_t scoreTotal = 0;
    float scorePulseAlpha = 0.0f;
};

class VulkanClearRenderer final {
public:
    VulkanClearRenderer() = default;
    ~VulkanClearRenderer();

    VulkanClearRenderer(const VulkanClearRenderer&) = delete;
    VulkanClearRenderer& operator=(const VulkanClearRenderer&) = delete;

    [[nodiscard]] bool initialize(
        ANativeWindow* window,
        AAssetManager* assetManager,
        JNIEnv* env,
        jobject javaActivity) noexcept;

    void shutdown() noexcept;

    void setPreferredFrameRate(
        float framesPerSecond) noexcept;

    [[nodiscard]] bool drawFrame(
        float timeSeconds,
        const VulkanCamera& camera,
        const VulkanHudState& hud,
        const VulkanSceneState& scene,
        const VulkanEnvironmentState& environment) noexcept;
    [[nodiscard]] bool ready() const noexcept;
    [[nodiscard]] bool deviceLost() const noexcept;

    // Game-thread bridge used by IntrinsicAdSystem/AdSurface. The placeholder
    // texture must already be bound by the loaded static map.
    [[nodiscard]] bool queueIntrinsicAdSurfaceCreative(
        const char* sourceTextureAssetPath,
        const char* replacementAssetPath) noexcept;

    [[nodiscard]] bool intrinsicAdSurfaceUploadBusy() const noexcept;

    // Measured on the previous completed frame. These are deliberately
    // renderer-owned so the PerformanceGovernor receives real workload data
    // instead of wall-clock frame cadence / guessed GPU cost.
    [[nodiscard]] float lastCpuRenderMs() const noexcept;
    [[nodiscard]] float lastGpuFrameMs() const noexcept;
    [[nodiscard]] float lastGpuPreWorldMs() const noexcept;
    [[nodiscard]] float lastGpuWorldMs() const noexcept;
    [[nodiscard]] float lastGpuCompositeUiMs() const noexcept;
    [[nodiscard]] bool gpuTimingAuthoritative() const noexcept;

private:
    struct FrameSync {
        VkSemaphore imageAvailable = VK_NULL_HANDLE;
        VkSemaphore renderFinished = VK_NULL_HANDLE;
        VkFence inFlight = VK_NULL_HANDLE;
    };

    struct UiPushConstants {
        float centerX = 0.0f;
        float centerY = 0.0f;
        float halfWidth = 0.1f;
        float halfHeight = 0.1f;

        float colorR = 1.0f;
        float colorG = 1.0f;
        float colorB = 1.0f;
        float colorA = 1.0f;

        float shape = 0.0f;
        float ringWidth = 0.15f;
        float padding0 = 0.0f;
        float padding1 = 0.0f;
    };

    struct PushConstants {
        float timeSeconds = 0.0f;
        float aspect = 1.0f;
        float horrorPulse = 0.0f;
        float materialId = 0.0f;

        float translationX = 0.0f;
        float translationY = 0.0f;
        float translationZ = 0.0f;
        float translationPadding = 0.0f;

        float scaleX = 1.0f;
        float scaleY = 1.0f;
        float scaleZ = 1.0f;
        float scalePadding = 0.0f;

        float cameraX = 0.0f;
        float cameraY = 0.14f;
        float cameraZ = -2.55f;
        float cameraYawRadians = 0.0f;

        float cameraPitchRadians = 0.0f;
        float verticalFovDegrees = 72.0f;
        float cameraPadding0 = 0.0f;
        float cameraPadding1 = 0.0f;

        float fogDensity = 0.0f;
        float lightningFlash = 0.0f;
        float wetness = 0.0f;
        float rainIntensity = 0.0f;

        float waterWavePhase = 0.0f;
        float waterFoamStrength = 0.0f;
        float waterReflectionStrength = 0.0f;
        float waterRefractionStrength = 0.0f;

        float waterRoughness = 0.10f;
        float waterQualityScale = 1.0f;
        float waterParticleScale = 1.0f;
        float waterFogScale = 1.0f;

        float reflectionPlaneX = 0.0f;
        float reflectionPlaneY = 1.0f;
        float reflectionPlaneZ = 0.0f;
        float reflectionPlaneDistance = 1.48f;
    };

    [[nodiscard]] bool createInstance() noexcept;
    [[nodiscard]] bool createSurface(ANativeWindow* window) noexcept;
    [[nodiscard]] bool selectPhysicalDevice() noexcept;
    [[nodiscard]] bool createDevice() noexcept;
    [[nodiscard]] bool createSwapchain() noexcept;
    [[nodiscard]] bool initializeFramePacing() noexcept;

    [[nodiscard]] bool chooseSurfaceFormat(
        VkSurfaceFormatKHR& out) const noexcept;

    [[nodiscard]] bool chooseDepthFormat(
        VkFormat& out) const noexcept;

    [[nodiscard]] bool findMemoryType(
        std::uint32_t typeBits,
        VkMemoryPropertyFlags required,
        std::uint32_t& outIndex) const noexcept;

    [[nodiscard]] bool createRenderPass() noexcept;
    [[nodiscard]] bool createUiRenderPass() noexcept;
    [[nodiscard]] bool createGraphicsPipeline() noexcept;
    [[nodiscard]] bool createSceneCompositePipeline() noexcept;
    [[nodiscard]] bool createUiPipeline() noexcept;
    [[nodiscard]] bool createUiBatchResources() noexcept;
    void destroyUiBatchResources() noexcept;

    [[nodiscard]] bool createShaderModuleFromAsset(
        const char* assetPath,
        VkShaderModule& outModule) noexcept;

    [[nodiscard]] bool createImageViews() noexcept;
    [[nodiscard]] bool createSceneColorResources() noexcept;
    [[nodiscard]] bool createSceneResolveResources() noexcept;
    [[nodiscard]] bool createDepthResources() noexcept;
    [[nodiscard]] bool createSceneCompositeDescriptors() noexcept;
    [[nodiscard]] bool createReflectionFallbackResources() noexcept;
    void destroyReflectionFallbackResources() noexcept;
    void updateReflectionDescriptor(VkImageView view) noexcept;
    [[nodiscard]] bool createReflectionTarget(
        float resolutionScale) noexcept;
    [[nodiscard]] bool createReflectionPassResources() noexcept;
    void destroyReflectionPassResources() noexcept;
    void destroyReflectionTarget() noexcept;
    [[nodiscard]] bool createFramebuffers() noexcept;
    [[nodiscard]] bool createUiFramebuffers() noexcept;
    [[nodiscard]] bool createCommandResources() noexcept;
    void destroySceneTargets() noexcept;
    [[nodiscard]] bool recreateSceneTargets(
        float renderScale) noexcept;
    void updateSceneExtent(
        float renderScale) noexcept;
    [[nodiscard]] bool createSyncObjects() noexcept;
    [[nodiscard]] bool createPerformanceQueries() noexcept;
    void destroyPerformanceQueries() noexcept;
    void resolvePerformanceQueries(
        std::uint32_t frameSlot) noexcept;

    void destroySwapchainResources() noexcept;

    [[nodiscard]] bool recreateSwapchain() noexcept;

    [[nodiscard]] bool recordDrawCommand(
        std::uint32_t imageIndex,
        std::uint32_t frameSlot,
        float timeSeconds,
        const VulkanCamera& camera,
        const VulkanHudState& hud,
        const VulkanSceneState& scene,
        const VulkanEnvironmentState& environment) noexcept;

    VkInstance instance_ = VK_NULL_HANDLE;
    VkSurfaceKHR surface_ = VK_NULL_HANDLE;
    VkPhysicalDevice physicalDevice_ = VK_NULL_HANDLE;
    VkDevice device_ = VK_NULL_HANDLE;

    std::uint32_t graphicsQueueFamily_ = UINT32_MAX;
    VkQueue graphicsQueue_ = VK_NULL_HANDLE;
    VkPhysicalDeviceType physicalDeviceType_ =
        VK_PHYSICAL_DEVICE_TYPE_OTHER;

    bool astcLdrSupported_ = false;
    VkSampleCountFlagBits preferredSceneMsaa_ =
        VK_SAMPLE_COUNT_1_BIT;
    std::uint32_t maxImageDimension2D_ = 0U;
    float deviceMaxSamplerAnisotropy_ = 1.0f;
    std::uint64_t deviceLocalMemoryBytes_ = 0U;

    VkSwapchainKHR swapchain_ = VK_NULL_HANDLE;
    VkFormat swapchainFormat_ = VK_FORMAT_UNDEFINED;
    VkFormat depthFormat_ = VK_FORMAT_UNDEFINED;
    VkExtent2D swapchainExtent_{};
    VkExtent2D sceneExtent_{};
    float activeRenderScale_ = 1.0f;

    VkRenderPass renderPass_ = VK_NULL_HANDLE;
    VkRenderPass uiRenderPass_ = VK_NULL_HANDLE;
    VkPipelineLayout pipelineLayout_ = VK_NULL_HANDLE;
    VkPipeline graphicsPipeline_ = VK_NULL_HANDLE;

    VkPipelineLayout sceneCompositePipelineLayout_ = VK_NULL_HANDLE;
    VkPipeline sceneCompositePipeline_ = VK_NULL_HANDLE;
    VkDescriptorSetLayout sceneCompositeDescriptorSetLayout_ = VK_NULL_HANDLE;
    VkDescriptorPool sceneCompositeDescriptorPool_ = VK_NULL_HANDLE;
    VkSampler sceneCompositeSampler_ = VK_NULL_HANDLE;

    VkPipelineLayout uiPipelineLayout_ = VK_NULL_HANDLE;
    VkPipeline uiPipeline_ = VK_NULL_HANDLE;
    VkPipeline uiBatchPipeline_ = VK_NULL_HANDLE;
    VkBuffer uiBatchVertexBuffer_ = VK_NULL_HANDLE;
    VkDeviceMemory uiBatchVertexMemory_ = VK_NULL_HANDLE;
    void* uiBatchMapped_ = nullptr;

    VkCommandPool commandPool_ = VK_NULL_HANDLE;

    VulkanStaticMeshRenderer sanctumMesh_{};
    VulkanStaticMeshRenderer weaponMesh_{};

    std::vector<VkImage> swapchainImages_;
    std::vector<VkImageView> imageViews_;

    // Main-scene MSAA color is transient and resolves directly into the
    // swapchain inside the render pass. It is empty on 1x devices/CI.
    std::vector<VkImage> sceneColorImages_;
    std::vector<VkDeviceMemory> sceneColorMemory_;
    std::vector<VkImageView> sceneColorViews_;

    // Single-sample world color that receives the MSAA resolve (or is drawn
    // directly on 1x devices) and is then sampled by the native-resolution
    // composite pass.
    std::vector<VkImage> sceneResolveImages_;
    std::vector<VkDeviceMemory> sceneResolveMemory_;
    std::vector<VkImageView> sceneResolveViews_;
    std::vector<VkDescriptorSet> sceneCompositeDescriptorSets_;

    std::vector<VkImage> depthImages_;
    std::vector<VkDeviceMemory> depthMemory_;
    std::vector<VkImageView> depthViews_;

    // Single bounded offscreen planar-reflection target. It is intentionally
    // shared/reused rather than allocating one texture per reflective surface.
    VkImage reflectionColorImage_ = VK_NULL_HANDLE;
    VkDeviceMemory reflectionColorMemory_ = VK_NULL_HANDLE;
    VkImageView reflectionColorView_ = VK_NULL_HANDLE;
    VkImage reflectionDepthImage_ = VK_NULL_HANDLE;
    VkDeviceMemory reflectionDepthMemory_ = VK_NULL_HANDLE;
    VkImageView reflectionDepthView_ = VK_NULL_HANDLE;
    VkExtent2D reflectionExtent_{};
    float reflectionTargetScale_ = 0.0f;
    float reflectionTargetPlaneX_ = 0.0f;
    float reflectionTargetPlaneY_ = 1.0f;
    float reflectionTargetPlaneZ_ = 0.0f;
    float reflectionTargetPlaneD_ = 0.0f;
    bool reflectionTargetHasPlane_ = false;
    std::uint64_t reflectionFrameCounter_ = 0;
    std::uint32_t reflectionAllocationBackoffFrames_ = 0;
    bool reflectionHasValidContents_ = false;
    std::uint32_t reflectionInvisibleFrames_ = 0;
    VkRenderPass reflectionRenderPass_ = VK_NULL_HANDLE;
    VkFramebuffer reflectionFramebuffer_ = VK_NULL_HANDLE;
    VkPipeline reflectionPipeline_ = VK_NULL_HANDLE;
    VkImage reflectionFallbackImage_ = VK_NULL_HANDLE;
    VkDeviceMemory reflectionFallbackMemory_ = VK_NULL_HANDLE;
    VkImageView reflectionFallbackView_ = VK_NULL_HANDLE;
    VkSampler reflectionSampler_ = VK_NULL_HANDLE;
    VkDescriptorSetLayout reflectionDescriptorSetLayout_ = VK_NULL_HANDLE;
    VkDescriptorPool reflectionDescriptorPool_ = VK_NULL_HANDLE;
    VkDescriptorSet reflectionDescriptorSet_ = VK_NULL_HANDLE;

    std::vector<VkFramebuffer> framebuffers_;
    std::vector<VkFramebuffer> uiFramebuffers_;
    std::vector<VkCommandBuffer> commandBuffers_;
    std::vector<VkFence> imageFences_;

    static constexpr std::uint32_t kFramesInFlight = 2;
    static constexpr std::uint32_t
        kGpuTimestampQueriesPerFrame = 4U;
    FrameSync frames_[kFramesInFlight]{};
    std::uint32_t frameIndex_ = 0;

    // Four timestamp cuts per in-flight frame: frame begin, end of
    // pre-world/reflection work, end of world rendering, and end of
    // composite/UI. Results are read only after that frame slot's fence
    // signals, so pass timing never stalls the GPU.
    VkQueryPool gpuTimestampQueryPool_ = VK_NULL_HANDLE;
    std::array<bool, kFramesInFlight> gpuTimestampValid_{};
    std::uint32_t timestampValidBits_ = 0;
    float timestampPeriodNs_ = 0.0f;
    float lastCpuRenderMs_ = 0.0f;
    float lastGpuFrameMs_ = 0.0f;
    float lastGpuPreWorldMs_ = 0.0f;
    float lastGpuWorldMs_ = 0.0f;
    float lastGpuCompositeUiMs_ = 0.0f;
    std::uint64_t performanceTelemetryFrame_ = 0;
    bool performanceTimingReadyLogged_ = false;
    std::uint64_t suboptimalFrameCount_ = 0;

    ANativeWindow* window_ = nullptr;
    AAssetManager* assetManager_ = nullptr;
    JNIEnv* jniEnv_ = nullptr;
    jobject javaActivity_ = nullptr;

    std::uint64_t refreshDurationNs_ = 0;
    std::uint64_t requestedSwapIntervalNs_ = 0;

    float preferredFrameRate_ = 0.0f;

    bool framePacingAttempted_ = false;
    bool swappyInitialized_ = false;
    bool initialized_ = false;
    bool deviceLost_ = false;
};

} // namespace xziel::android
