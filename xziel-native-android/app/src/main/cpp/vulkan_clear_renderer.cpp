#include "vulkan_clear_renderer.hpp"

#include <android/log.h>
#include <swappy/swappyVk.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <limits>
#include <vector>

namespace xziel::android {

namespace {

constexpr const char* kTag = "XzielVulkan";

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

bool ok(VkResult result) noexcept {
    return result == VK_SUCCESS;
}

struct UiBatchVertex {
    float positionX = 0.0f;
    float positionY = 0.0f;
    float localX = 0.0f;
    float localY = 0.0f;
    float colorR = 1.0f;
    float colorG = 1.0f;
    float colorB = 1.0f;
    float colorA = 1.0f;
    float shape = 0.0f;
    float ringWidth = 0.10f;
};

static_assert(
    sizeof(UiBatchVertex) == 40U,
    "UI batch vertex layout must remain 40 bytes");

constexpr std::uint32_t kUiBatchVerticesPerPrimitive = 6U;
constexpr std::uint32_t kUiBatchMaxPrimitives = 256U;
constexpr std::uint32_t kUiBatchVerticesPerFrame =
    kUiBatchVerticesPerPrimitive *
    kUiBatchMaxPrimitives;

constexpr std::array<std::array<float, 2>, 6> kUiQuad{{
    {{-1.0f, -1.0f}},
    {{ 1.0f, -1.0f}},
    {{ 1.0f,  1.0f}},
    {{-1.0f, -1.0f}},
    {{ 1.0f,  1.0f}},
    {{-1.0f,  1.0f}},
}};

VkCompositeAlphaFlagBitsKHR chooseCompositeAlpha(
    VkCompositeAlphaFlagsKHR supported) noexcept {
    constexpr std::array<VkCompositeAlphaFlagBitsKHR, 4> order{
        VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
        VK_COMPOSITE_ALPHA_INHERIT_BIT_KHR,
        VK_COMPOSITE_ALPHA_PRE_MULTIPLIED_BIT_KHR,
        VK_COMPOSITE_ALPHA_POST_MULTIPLIED_BIT_KHR,
    };

    for (const auto value : order) {
        if ((supported & value) != 0) {
            return value;
        }
    }

    return VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
}

} // namespace

VulkanClearRenderer::~VulkanClearRenderer() {
    shutdown();
}

bool VulkanClearRenderer::initialize(
    ANativeWindow* window,
    AAssetManager* assetManager,
    JNIEnv* env,
    jobject javaActivity) noexcept {
    deviceLost_ = false;
    shutdown();

    if (window == nullptr || assetManager == nullptr) {
        logError("initialize requires window + asset manager");
        return false;
    }

    window_ = window;
    assetManager_ = assetManager;
    jniEnv_ = env;
    javaActivity_ = javaActivity;
    ANativeWindow_acquire(window_);

    if (!createInstance() ||
        !createSurface(window_) ||
        !selectPhysicalDevice() ||
        !createDevice() ||
        !createSwapchain() ||
        !createRenderPass() ||
        !createUiRenderPass() ||
        !createGraphicsPipeline() ||
        !createSceneCompositePipeline() ||
        !createUiPipeline() ||
        !createUiBatchResources() ||
        !createImageViews() ||
        !createSceneColorResources() ||
        !createSceneResolveResources() ||
        !createDepthResources() ||
        !createCommandResources() ||
        !createPerformanceQueries() ||
        !createReflectionFallbackResources() ||
        !createFramebuffers() ||
        !createUiFramebuffers() ||
        !createSceneCompositeDescriptors() ||
        !createSyncObjects()) {
        logError("Vulkan initialization failed");
        shutdown();
        return false;
    }

    // The HQ Sanctum asset is optional for the generic engine prototype.
    // A Sanctum build packages this file and immediately promotes it to world
    // visual authority without requiring BSP/Vril/GL4ES.
    (void) sanctumMesh_.initialize(
        physicalDevice_,
        device_,
        graphicsQueue_,
        graphicsQueueFamily_,
        commandPool_,
        renderPass_,
        preferredSceneMsaa_,
        assetManager_,
        "models/xziel/sanctum/sanctum.xzsm");

    (void) weaponMesh_.initialize(
        physicalDevice_,
        device_,
        graphicsQueue_,
        graphicsQueueFamily_,
        commandPool_,
        renderPass_,
        preferredSceneMsaa_,
        assetManager_,
        "models/xziel/weapons/standard_rifle.xzsm");

    initialized_ = true;
    logInfo("XZIEL_VULKAN_3D_READY");
    return true;
}

void VulkanClearRenderer::shutdown() noexcept {
    initialized_ = false;

    if (device_ != VK_NULL_HANDLE) {
        vkDeviceWaitIdle(device_);
    }

    // Destroy native world/viewmodel resources while the device/render pass/
    // command pool they were created from are still alive.
    weaponMesh_.shutdown();
    sanctumMesh_.shutdown();

    for (auto& frame : frames_) {
        if (frame.imageAvailable != VK_NULL_HANDLE &&
            device_ != VK_NULL_HANDLE) {
            vkDestroySemaphore(
                device_,
                frame.imageAvailable,
                nullptr);
        }

        if (frame.renderFinished != VK_NULL_HANDLE &&
            device_ != VK_NULL_HANDLE) {
            vkDestroySemaphore(
                device_,
                frame.renderFinished,
                nullptr);
        }

        if (frame.inFlight != VK_NULL_HANDLE &&
            device_ != VK_NULL_HANDLE) {
            vkDestroyFence(
                device_,
                frame.inFlight,
                nullptr);
        }

        frame = {};
    }

    destroyPerformanceQueries();
    destroySwapchainResources();
    destroyUiBatchResources();

    if (commandPool_ != VK_NULL_HANDLE &&
        device_ != VK_NULL_HANDLE) {
        vkDestroyCommandPool(
            device_,
            commandPool_,
            nullptr);
        commandPool_ = VK_NULL_HANDLE;
    }

    if (device_ != VK_NULL_HANDLE) {
        vkDestroyDevice(
            device_,
            nullptr);
        device_ = VK_NULL_HANDLE;
    }

    graphicsQueue_ = VK_NULL_HANDLE;
    physicalDevice_ = VK_NULL_HANDLE;
    graphicsQueueFamily_ = UINT32_MAX;
    physicalDeviceType_ =
        VK_PHYSICAL_DEVICE_TYPE_OTHER;

    if (surface_ != VK_NULL_HANDLE &&
        instance_ != VK_NULL_HANDLE) {
        vkDestroySurfaceKHR(
            instance_,
            surface_,
            nullptr);
        surface_ = VK_NULL_HANDLE;
    }

    if (instance_ != VK_NULL_HANDLE) {
        vkDestroyInstance(
            instance_,
            nullptr);
        instance_ = VK_NULL_HANDLE;
    }

    if (window_ != nullptr) {
        ANativeWindow_release(window_);
        window_ = nullptr;
    }

    assetManager_ = nullptr;
    jniEnv_ = nullptr;
    javaActivity_ = nullptr;
    refreshDurationNs_ = 0;
    swappyInitialized_ = false;
    depthFormat_ = VK_FORMAT_UNDEFINED;
    frameIndex_ = 0;
    timestampValidBits_ = 0;
    timestampPeriodNs_ = 0.0f;
    astcLdrSupported_ = false;
    preferredSceneMsaa_ = VK_SAMPLE_COUNT_1_BIT;
    maxImageDimension2D_ = 0U;
    deviceMaxSamplerAnisotropy_ = 1.0f;
    deviceLocalMemoryBytes_ = 0U;
    lastCpuRenderMs_ = 0.0f;
    lastGpuFrameMs_ = 0.0f;
    lastGpuPreWorldMs_ = 0.0f;
    lastGpuWorldMs_ = 0.0f;
    lastGpuCompositeUiMs_ = 0.0f;
    performanceTelemetryFrame_ = 0;
    performanceTimingReadyLogged_ = false;
    suboptimalFrameCount_ = 0;
    framePacingAttempted_ = false;
}

void VulkanClearRenderer::setPreferredFrameRate(
    float framesPerSecond) noexcept {
    if (!std::isfinite(framesPerSecond) ||
        framesPerSecond <= 0.0f) {
        return;
    }

    preferredFrameRate_ =
        std::clamp(
            framesPerSecond,
            30.0f,
            240.0f);

    if (!swappyInitialized_ ||
        device_ == VK_NULL_HANDLE ||
        swapchain_ == VK_NULL_HANDLE) {
        return;
    }

    const double targetNs =
        1000000000.0 /
        static_cast<double>(
            preferredFrameRate_);

    std::uint64_t intervalNs =
        static_cast<std::uint64_t>(
            std::llround(
                targetNs));

    if (refreshDurationNs_ > 0) {
        intervalNs =
            std::max(
                intervalNs,
                refreshDurationNs_);
    }

    if (intervalNs ==
        requestedSwapIntervalNs_) {
        return;
    }

    SwappyVk_setSwapIntervalNS(
        device_,
        swapchain_,
        intervalNs);

    requestedSwapIntervalNs_ =
        intervalNs;
}

bool VulkanClearRenderer::drawFrame(
    float timeSeconds,
    const VulkanCamera& camera,
    const VulkanHudState& hud,
    const VulkanSceneState& scene,
    const VulkanEnvironmentState& environment) noexcept {
    if (!initialized_ ||
        device_ == VK_NULL_HANDLE ||
        swapchain_ == VK_NULL_HANDLE) {
        return false;
    }

    const auto waitForDeviceIdle = [&]() noexcept {
        const VkResult idleResult =
            vkDeviceWaitIdle(
                device_);

        if (idleResult == VK_ERROR_DEVICE_LOST) {
            deviceLost_ = true;
        }

        return ok(idleResult);
    };

    const float requestedRenderScale =
        std::isfinite(environment.renderScale)
        ? std::clamp(environment.renderScale, 0.50f, 1.0f)
        : 1.0f;

    if (std::abs(
            requestedRenderScale -
            activeRenderScale_) > 0.015f) {
        if (!waitForDeviceIdle() ||
            !recreateSceneTargets(
                requestedRenderScale)) {
            return false;
        }
    }

    // Keep one reusable offscreen reflection target synchronized with the
    // adaptive workload. Allocation happens only when the scale changes, never
    // as per-frame churn. Failure is deliberately non-fatal: probe/shader
    // fallback remains available on memory-constrained devices.
    const float reflectionCoverage =
        std::clamp(
            environment.planarReflectionScreenCoverage,
            0.0f,
            1.0f);
    const bool reflectionContributes =
        environment.planarReflectionVisible &&
        reflectionCoverage > 0.0025f;

    if (reflectionContributes) {
        reflectionInvisibleFrames_ = 0;
    } else if (reflectionInvisibleFrames_ < UINT32_MAX) {
        ++reflectionInvisibleFrames_;
    }

    const float qualityReflectionScale =
        std::clamp(
            environment.planarReflectionScale,
            0.0f,
            1.0f);
    const bool targetWantedByQuality =
        environment.maxPlanarReflectionPasses > 0 &&
        qualityReflectionScale > 0.0f;

    // Quality policy and temporary camera visibility are deliberately
    // separate. Looking away keeps a valid target warm for a short grace
    // period; a quality/thermal downgrade releases it immediately.
    const float requestedReflectionScale =
        targetWantedByQuality
        ? qualityReflectionScale
        : 0.0f;

    float requestedPlaneX = environment.planarPlaneNormalX;
    float requestedPlaneY = environment.planarPlaneNormalY;
    float requestedPlaneZ = environment.planarPlaneNormalZ;
    float requestedPlaneD = environment.planarPlaneDistance;
    const float requestedPlaneLength = std::sqrt(
        requestedPlaneX * requestedPlaneX +
        requestedPlaneY * requestedPlaneY +
        requestedPlaneZ * requestedPlaneZ);
    if (!std::isfinite(requestedPlaneLength) || requestedPlaneLength < 0.0001f) {
        requestedPlaneX = 0.0f;
        requestedPlaneY = 1.0f;
        requestedPlaneZ = 0.0f;
        requestedPlaneD = 1.48f;
    } else {
        const float inverseRequestedPlaneLength = 1.0f / requestedPlaneLength;
        requestedPlaneX *= inverseRequestedPlaneLength;
        requestedPlaneY *= inverseRequestedPlaneLength;
        requestedPlaneZ *= inverseRequestedPlaneLength;
        requestedPlaneD = std::isfinite(requestedPlaneD)
            ? requestedPlaneD * inverseRequestedPlaneLength
            : 0.0f;
    }

    // A single reusable target must never be treated as valid after the
    // planner switches ownership to a different surface plane. Without this,
    // a mirror can briefly sample the previous water capture (or vice versa)
    // until the normal temporal refresh interval expires.
    const bool reflectionPlaneChanged =
        reflectionTargetHasPlane_ &&
        (std::abs(requestedPlaneX - reflectionTargetPlaneX_) > 0.0005f ||
         std::abs(requestedPlaneY - reflectionTargetPlaneY_) > 0.0005f ||
         std::abs(requestedPlaneZ - reflectionTargetPlaneZ_) > 0.0005f ||
         std::abs(requestedPlaneD - reflectionTargetPlaneD_) > 0.002f);

    if (reflectionContributes &&
        (!reflectionTargetHasPlane_ || reflectionPlaneChanged)) {
        reflectionTargetPlaneX_ = requestedPlaneX;
        reflectionTargetPlaneY_ = requestedPlaneY;
        reflectionTargetPlaneZ_ = requestedPlaneZ;
        reflectionTargetPlaneD_ = requestedPlaneD;
        reflectionTargetHasPlane_ = true;
        reflectionHasValidContents_ = false;
        reflectionFrameCounter_ = 0;
    }

    if (reflectionAllocationBackoffFrames_ > 0) {
        --reflectionAllocationBackoffFrames_;
    }

    const bool shouldAllocateReflectionTarget =
        targetWantedByQuality &&
        reflectionContributes &&
        reflectionAllocationBackoffFrames_ == 0 &&
        (reflectionColorImage_ == VK_NULL_HANDLE ||
         std::abs(
             requestedReflectionScale -
             reflectionTargetScale_) > 0.025f);

    if (shouldAllocateReflectionTarget) {
        if (!waitForDeviceIdle()) {
            return false;
        }
        const bool reflectionTargetReady =
            createReflectionTarget(
                requestedReflectionScale);
        if (!reflectionTargetReady ||
            reflectionColorImage_ == VK_NULL_HANDLE) {
            // Allocation failure is a supported mobile fallback, not a reason
            // to hammer vkAllocateMemory every frame. Retry after roughly two
            // seconds at 60 Hz while the persistent fallback stays sampleable.
            reflectionAllocationBackoffFrames_ = 120U;
        } else {
            reflectionAllocationBackoffFrames_ = 0U;
            // createReflectionTarget() intentionally tears down the previous
            // target first, which also clears its plane ownership cache.
            // Restore ownership immediately so the next frame does not
            // invalidate a freshly captured target a second time.
            reflectionTargetPlaneX_ = requestedPlaneX;
            reflectionTargetPlaneY_ = requestedPlaneY;
            reflectionTargetPlaneZ_ = requestedPlaneZ;
            reflectionTargetPlaneD_ = requestedPlaneD;
            reflectionTargetHasPlane_ = true;
        }
    } else if (!targetWantedByQuality &&
               reflectionColorImage_ != VK_NULL_HANDLE) {
        if (!waitForDeviceIdle()) {
            return false;
        }
        destroyReflectionTarget();
    } else if (!reflectionContributes &&
               reflectionColorImage_ != VK_NULL_HANDLE &&
               reflectionInvisibleFrames_ >= 90U) {
        // Camera-facing changes are transient: debounce only this case so a
        // quick turn never creates a device-idle destroy/reallocate loop.
        if (!waitForDeviceIdle()) {
            return false;
        }
        destroyReflectionTarget();
    }

    const std::uint32_t frameSlot =
        frameIndex_ % kFramesInFlight;

    auto& frame =
        frames_[frameSlot];

    VkResult result =
        vkWaitForFences(
            device_,
            1,
            &frame.inFlight,
            VK_TRUE,
            UINT64_MAX);

    if (!ok(result)) {
        if (result == VK_ERROR_DEVICE_LOST) {
            deviceLost_ = true;
        }
        logError("vkWaitForFences failed");
        return false;
    }

    // The fence guarantees this frame slot's previous timestamp pair is
    // complete. Reading here avoids VK_QUERY_RESULT_WAIT_BIT and therefore
    // does not create a measurement-induced GPU stall.
    resolvePerformanceQueries(
        frameSlot);

    std::uint32_t imageIndex = 0;

    result =
        vkAcquireNextImageKHR(
            device_,
            swapchain_,
            UINT64_MAX,
            frame.imageAvailable,
            VK_NULL_HANDLE,
            &imageIndex);

    if (result == VK_ERROR_OUT_OF_DATE_KHR) {
        return recreateSwapchain();
    }

    const bool suboptimal =
        result == VK_SUBOPTIMAL_KHR;

    if (result != VK_SUCCESS && !suboptimal) {
        if (result == VK_ERROR_DEVICE_LOST) {
            deviceLost_ = true;
        }
        logError("vkAcquireNextImageKHR failed");
        return false;
    }

    if (imageIndex >= imageFences_.size()) {
        logError("invalid swapchain image index");
        return false;
    }

    if (imageFences_[imageIndex] != VK_NULL_HANDLE) {
        result =
            vkWaitForFences(
                device_,
                1,
                &imageFences_[imageIndex],
                VK_TRUE,
                UINT64_MAX);

        if (!ok(result)) {
            if (result == VK_ERROR_DEVICE_LOST) {
                deviceLost_ = true;
            }
            logError("image ownership fence wait failed");
            return false;
        }
    }

    imageFences_[imageIndex] =
        frame.inFlight;

    result =
        vkResetFences(
            device_,
            1,
            &frame.inFlight);

    if (!ok(result)) {
        if (result == VK_ERROR_DEVICE_LOST) {
            deviceLost_ = true;
        }
        logError("vkResetFences failed");
        return false;
    }

    const auto cpuRenderStart =
        std::chrono::steady_clock::now();

    if (!recordDrawCommand(
            imageIndex,
            frameSlot,
            timeSeconds,
            camera,
            hud,
            scene,
            environment)) {
        return false;
    }

    const VkPipelineStageFlags waitStage =
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;

    VkSubmitInfo submit{
        VK_STRUCTURE_TYPE_SUBMIT_INFO
    };
    submit.waitSemaphoreCount = 1;
    submit.pWaitSemaphores =
        &frame.imageAvailable;
    submit.pWaitDstStageMask =
        &waitStage;
    submit.commandBufferCount = 1;
    submit.pCommandBuffers =
        &commandBuffers_[imageIndex];
    submit.signalSemaphoreCount = 1;
    submit.pSignalSemaphores =
        &frame.renderFinished;

    result =
        vkQueueSubmit(
            graphicsQueue_,
            1,
            &submit,
            frame.inFlight);

    const auto cpuRenderEnd =
        std::chrono::steady_clock::now();

    lastCpuRenderMs_ =
        std::chrono::duration<float, std::milli>(
            cpuRenderEnd -
            cpuRenderStart).count();

    if (!ok(result)) {
        if (result == VK_ERROR_DEVICE_LOST) {
            deviceLost_ = true;
        }
        logError("vkQueueSubmit failed");
        return false;
    }

    VkPresentInfoKHR present{
        VK_STRUCTURE_TYPE_PRESENT_INFO_KHR
    };
    present.waitSemaphoreCount = 1;
    present.pWaitSemaphores =
        &frame.renderFinished;
    present.swapchainCount = 1;
    present.pSwapchains =
        &swapchain_;
    present.pImageIndices =
        &imageIndex;

    result =
        swappyInitialized_
        ? SwappyVk_queuePresent(
              graphicsQueue_,
              &present)
        : vkQueuePresentKHR(
              graphicsQueue_,
              &present);

    if (result == VK_ERROR_OUT_OF_DATE_KHR) {
        logInfo("XZIEL_SWAPCHAIN_RECREATE_OUT_OF_DATE");
        if (!recreateSwapchain()) {
            return false;
        }
    } else if (result != VK_SUCCESS &&
               result != VK_SUBOPTIMAL_KHR) {
        if (result == VK_ERROR_DEVICE_LOST) {
            deviceLost_ = true;
        }
        logError("vkQueuePresentKHR failed");
        return false;
    } else if (result == VK_SUBOPTIMAL_KHR ||
               suboptimal) {
        // Android can report a swapchain as permanently SUBOPTIMAL when the
        // app intentionally uses IDENTITY pre-transform and lets
        // SurfaceFlinger own display rotation. Recreating an unchanged
        // 2400x1080 swapchain every frame can never fix that condition and
        // churns render passes/pipelines. OUT_OF_DATE and lifecycle events
        // remain authoritative for real surface changes.
        ++suboptimalFrameCount_;
        if (suboptimalFrameCount_ == 1U ||
            suboptimalFrameCount_ % 120U == 0U) {
            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_SWAPCHAIN_SUBOPTIMAL_DEFERRED count=%llu extent=%ux%u",
                static_cast<unsigned long long>(
                    suboptimalFrameCount_),
                swapchainExtent_.width,
                swapchainExtent_.height);
        }
    } else {
        suboptimalFrameCount_ = 0U;
    }

    ++frameIndex_;
    ++performanceTelemetryFrame_;

    // Swappy startup is deliberately delayed until the renderer has presented
    // healthy frames. Software/CPU Vulkan in CI skips it completely because
    // Choreographer bootstrap there can stall the GameActivity thread.
    if (!swappyInitialized_ &&
        !framePacingAttempted_ &&
        frameIndex_ >= 2U) {
        framePacingAttempted_ = true;

        if (physicalDeviceType_ ==
            VK_PHYSICAL_DEVICE_TYPE_CPU) {
            logInfo(
                "XZIEL_FRAME_PACING_SKIPPED_CPU");
        } else if (initializeFramePacing()) {
            logInfo(
                "XZIEL_FRAME_PACING_READY");
        } else {
            logInfo(
                "XZIEL_FRAME_PACING_UNAVAILABLE");
        }
    }

    if (performanceTelemetryFrame_ % 120U == 0U) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_PERF_TIMING cpu_render_ms=%.3f gpu_frame_ms=%.3f gpu_preworld_ms=%.3f gpu_world_ms=%.3f gpu_composite_ui_ms=%.3f gpu_authoritative=%d",
            static_cast<double>(lastCpuRenderMs_),
            static_cast<double>(lastGpuFrameMs_),
            static_cast<double>(lastGpuPreWorldMs_),
            static_cast<double>(lastGpuWorldMs_),
            static_cast<double>(lastGpuCompositeUiMs_),
            gpuTimingAuthoritative() ? 1 : 0);
    }

    return true;
}

bool VulkanClearRenderer::ready() const noexcept {
    return initialized_;
}

bool VulkanClearRenderer::deviceLost() const noexcept {
    return deviceLost_;
}

bool VulkanClearRenderer::queueIntrinsicAdSurfaceCreative(
    const char* sourceTextureAssetPath,
    const char* replacementAssetPath) noexcept {
    if (!ready_ ||
        assetManager_ == nullptr ||
        sourceTextureAssetPath == nullptr ||
        replacementAssetPath == nullptr) {
        return false;
    }

    return sanctumMesh_.queueRuntimeTextureReplacement(
        assetManager_,
        sourceTextureAssetPath,
        replacementAssetPath);
}

bool VulkanClearRenderer::intrinsicAdSurfaceUploadBusy() const noexcept {
    return sanctumMesh_.runtimeTextureReplacementBusy();
}


float VulkanClearRenderer::lastCpuRenderMs() const noexcept {
    return lastCpuRenderMs_;
}

float VulkanClearRenderer::lastGpuFrameMs() const noexcept {
    return lastGpuFrameMs_;
}

float VulkanClearRenderer::lastGpuPreWorldMs() const noexcept {
    return lastGpuPreWorldMs_;
}

float VulkanClearRenderer::lastGpuWorldMs() const noexcept {
    return lastGpuWorldMs_;
}

float VulkanClearRenderer::lastGpuCompositeUiMs() const noexcept {
    return lastGpuCompositeUiMs_;
}

bool VulkanClearRenderer::gpuTimingAuthoritative() const noexcept {
    return
        physicalDevice_ != VK_NULL_HANDLE &&
        physicalDeviceType_ != VK_PHYSICAL_DEVICE_TYPE_CPU &&
        gpuTimestampQueryPool_ != VK_NULL_HANDLE &&
        timestampValidBits_ > 0U &&
        timestampPeriodNs_ > 0.0f;
}

bool VulkanClearRenderer::createInstance() noexcept {
    constexpr std::array<const char*, 2>
        extensions{
            VK_KHR_SURFACE_EXTENSION_NAME,
            VK_KHR_ANDROID_SURFACE_EXTENSION_NAME,
        };

    VkApplicationInfo appInfo{
        VK_STRUCTURE_TYPE_APPLICATION_INFO
    };
    appInfo.pApplicationName =
        "Xziel Engine Prototype";
    appInfo.applicationVersion =
        VK_MAKE_API_VERSION(0, 0, 0, 2);
    appInfo.pEngineName =
        "Xziel Engine";
    appInfo.engineVersion =
        VK_MAKE_API_VERSION(0, 0, 0, 2);
    appInfo.apiVersion =
        VK_API_VERSION_1_1;

    VkInstanceCreateInfo createInfo{
        VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO
    };
    createInfo.pApplicationInfo =
        &appInfo;
    createInfo.enabledExtensionCount =
        static_cast<std::uint32_t>(
            extensions.size());
    createInfo.ppEnabledExtensionNames =
        extensions.data();

    const VkResult result =
        vkCreateInstance(
            &createInfo,
            nullptr,
            &instance_);

    if (!ok(result)) {
        logError("vkCreateInstance failed");
        return false;
    }

    return true;
}

bool VulkanClearRenderer::createSurface(
    ANativeWindow* window) noexcept {
    VkAndroidSurfaceCreateInfoKHR createInfo{
        VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR
    };
    createInfo.window = window;

    const VkResult result =
        vkCreateAndroidSurfaceKHR(
            instance_,
            &createInfo,
            nullptr,
            &surface_);

    if (!ok(result)) {
        logError("vkCreateAndroidSurfaceKHR failed");
        return false;
    }

    return true;
}

bool VulkanClearRenderer::selectPhysicalDevice() noexcept {
    std::uint32_t count = 0;

    VkResult result =
        vkEnumeratePhysicalDevices(
            instance_,
            &count,
            nullptr);

    if (!ok(result) || count == 0) {
        logError("No Vulkan physical device found");
        return false;
    }

    std::vector<VkPhysicalDevice> devices(count);

    result =
        vkEnumeratePhysicalDevices(
            instance_,
            &count,
            devices.data());

    if (!ok(result)) {
        logError("vkEnumeratePhysicalDevices failed");
        return false;
    }

    for (const auto candidate : devices) {
        VkPhysicalDeviceProperties properties{};
        vkGetPhysicalDeviceProperties(
            candidate,
            &properties);

        if (VK_API_VERSION_MAJOR(
                properties.apiVersion) < 1 ||
            (VK_API_VERSION_MAJOR(
                 properties.apiVersion) == 1 &&
             VK_API_VERSION_MINOR(
                 properties.apiVersion) < 1)) {
            continue;
        }

        std::uint32_t extensionCount = 0;

        if (!ok(
                vkEnumerateDeviceExtensionProperties(
                    candidate,
                    nullptr,
                    &extensionCount,
                    nullptr))) {
            continue;
        }

        std::vector<VkExtensionProperties>
            extensions(extensionCount);

        if (!ok(
                vkEnumerateDeviceExtensionProperties(
                    candidate,
                    nullptr,
                    &extensionCount,
                    extensions.data()))) {
            continue;
        }

        bool hasSwapchain = false;

        for (const auto& extension : extensions) {
            if (std::strcmp(
                    extension.extensionName,
                    VK_KHR_SWAPCHAIN_EXTENSION_NAME) == 0) {
                hasSwapchain = true;
                break;
            }
        }

        if (!hasSwapchain) {
            continue;
        }

        std::uint32_t queueCount = 0;

        vkGetPhysicalDeviceQueueFamilyProperties(
            candidate,
            &queueCount,
            nullptr);

        std::vector<VkQueueFamilyProperties>
            queues(queueCount);

        vkGetPhysicalDeviceQueueFamilyProperties(
            candidate,
            &queueCount,
            queues.data());

        for (std::uint32_t i = 0;
             i < queueCount;
             ++i) {
            VkBool32 present = VK_FALSE;

            if (!ok(
                    vkGetPhysicalDeviceSurfaceSupportKHR(
                        candidate,
                        i,
                        surface_,
                        &present))) {
                continue;
            }

            const bool graphics =
                (queues[i].queueFlags &
                 VK_QUEUE_GRAPHICS_BIT) != 0;

            if (graphics && present == VK_TRUE) {
                physicalDevice_ = candidate;
                graphicsQueueFamily_ = i;
                physicalDeviceType_ =
                    properties.deviceType;

                // Timestamp support is a queue-family property. Keep the
                // selected queue's valid-bit count and physical-device period
                // so the performance governor can consume real GPU duration.
                timestampValidBits_ =
                    queues[i].timestampValidBits;
                timestampPeriodNs_ =
                    properties.limits.timestampPeriod;

                VkPhysicalDeviceFeatures features{};
                vkGetPhysicalDeviceFeatures(
                    candidate,
                    &features);

                astcLdrSupported_ =
                    features.textureCompressionASTC_LDR ==
                    VK_TRUE;

                maxImageDimension2D_ =
                    properties.limits.maxImageDimension2D;

                deviceMaxSamplerAnisotropy_ =
                    features.samplerAnisotropy == VK_TRUE
                    ? properties.limits.maxSamplerAnisotropy
                    : 1.0f;

                const VkSampleCountFlags commonSamples =
                    properties.limits.framebufferColorSampleCounts &
                    properties.limits.framebufferDepthSampleCounts;

                preferredSceneMsaa_ =
                    physicalDeviceType_ ==
                        VK_PHYSICAL_DEVICE_TYPE_CPU
                    ? VK_SAMPLE_COUNT_1_BIT
                    : ((commonSamples &
                        VK_SAMPLE_COUNT_4_BIT) != 0U
                        ? VK_SAMPLE_COUNT_4_BIT
                        : ((commonSamples &
                            VK_SAMPLE_COUNT_2_BIT) != 0U
                            ? VK_SAMPLE_COUNT_2_BIT
                            : VK_SAMPLE_COUNT_1_BIT));

                VkPhysicalDeviceMemoryProperties memory{};
                vkGetPhysicalDeviceMemoryProperties(
                    candidate,
                    &memory);

                deviceLocalMemoryBytes_ = 0U;
                for (std::uint32_t heapIndex = 0U;
                     heapIndex < memory.memoryHeapCount;
                     ++heapIndex) {
                    if ((memory.memoryHeaps[heapIndex].flags &
                         VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) != 0U) {
                        deviceLocalMemoryBytes_ +=
                            memory.memoryHeaps[heapIndex].size;
                    }
                }

                __android_log_print(
                    ANDROID_LOG_INFO,
                    kTag,
                    "XZIEL_GPU_CAPS name=%s vendor=0x%x device=0x%x api=%u.%u.%u astc=%d msaa=%u max_tex=%u aniso=%.1f local_mb=%llu timestamp_bits=%u timestamp_ns=%.3f",
                    properties.deviceName,
                    properties.vendorID,
                    properties.deviceID,
                    VK_API_VERSION_MAJOR(properties.apiVersion),
                    VK_API_VERSION_MINOR(properties.apiVersion),
                    VK_API_VERSION_PATCH(properties.apiVersion),
                    astcLdrSupported_ ? 1 : 0,
                    static_cast<unsigned int>(preferredSceneMsaa_),
                    maxImageDimension2D_,
                    static_cast<double>(deviceMaxSamplerAnisotropy_),
                    static_cast<unsigned long long>(
                        deviceLocalMemoryBytes_ /
                        (1024ULL * 1024ULL)),
                    timestampValidBits_,
                    static_cast<double>(timestampPeriodNs_));

                return true;
            }
        }
    }

    logError(
        "No Vulkan 1.1 device supports graphics + present + swapchain");
    return false;
}

bool VulkanClearRenderer::createDevice() noexcept {
    constexpr float priority = 1.0f;

    VkDeviceQueueCreateInfo queueInfo{
        VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO
    };
    queueInfo.queueFamilyIndex =
        graphicsQueueFamily_;
    queueInfo.queueCount = 1;
    queueInfo.pQueuePriorities =
        &priority;

    std::uint32_t availableExtensionCount = 0;
    if (!ok(
            vkEnumerateDeviceExtensionProperties(
                physicalDevice_,
                nullptr,
                &availableExtensionCount,
                nullptr))) {
        logError("device extension count query failed");
        return false;
    }

    std::vector<VkExtensionProperties>
        availableExtensions(
            availableExtensionCount);

    if (availableExtensionCount > 0 &&
        !ok(
            vkEnumerateDeviceExtensionProperties(
                physicalDevice_,
                nullptr,
                &availableExtensionCount,
                availableExtensions.data()))) {
        logError("device extension list query failed");
        return false;
    }

    std::uint32_t swappyExtensionCount = 0;
    SwappyVk_determineDeviceExtensions(
        physicalDevice_,
        availableExtensionCount,
        availableExtensions.empty()
            ? nullptr
            : availableExtensions.data(),
        &swappyExtensionCount,
        nullptr);

    std::vector<std::array<
        char,
        VK_MAX_EXTENSION_NAME_SIZE + 1U>>
        swappyExtensionStorage(
            swappyExtensionCount);

    std::vector<char*>
        swappyExtensionNames(
            swappyExtensionCount);

    for (std::uint32_t i = 0;
         i < swappyExtensionCount;
         ++i) {
        swappyExtensionStorage[i].fill('\0');
        swappyExtensionNames[i] =
            swappyExtensionStorage[i].data();
    }

    if (swappyExtensionCount > 0) {
        std::uint32_t requestedCount =
            swappyExtensionCount;

        SwappyVk_determineDeviceExtensions(
            physicalDevice_,
            availableExtensionCount,
            availableExtensions.data(),
            &requestedCount,
            swappyExtensionNames.data());

        swappyExtensionCount =
            std::min(
                swappyExtensionCount,
                requestedCount);
    }

    std::vector<const char*>
        enabledExtensions;
    enabledExtensions.reserve(
        static_cast<std::size_t>(
            swappyExtensionCount) + 1U);

    enabledExtensions.push_back(
        VK_KHR_SWAPCHAIN_EXTENSION_NAME);

    for (std::uint32_t i = 0;
         i < swappyExtensionCount;
         ++i) {
        const char* name =
            swappyExtensionNames[i];

        if (name == nullptr ||
            name[0] == '\0') {
            continue;
        }

        bool duplicate = false;
        for (const char* existing :
             enabledExtensions) {
            if (std::strcmp(
                    existing,
                    name) == 0) {
                duplicate = true;
                break;
            }
        }

        if (!duplicate) {
            enabledExtensions.push_back(
                name);
        }
    }

    VkPhysicalDeviceFeatures availableFeatures{};
    vkGetPhysicalDeviceFeatures(
        physicalDevice_,
        &availableFeatures);

    VkPhysicalDeviceFeatures enabledFeatures{};
    enabledFeatures.samplerAnisotropy =
        availableFeatures.samplerAnisotropy;
    // Keep this optional: capable mobile GPUs can submit each compatible
    // static draw group with one vkCmdDrawIndexedIndirect call, while older
    // devices retain the direct-draw fallback.
    enabledFeatures.multiDrawIndirect =
        availableFeatures.multiDrawIndirect;

    VkDeviceCreateInfo createInfo{
        VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO
    };
    createInfo.queueCreateInfoCount = 1;
    createInfo.pQueueCreateInfos =
        &queueInfo;
    createInfo.enabledExtensionCount =
        static_cast<std::uint32_t>(
            enabledExtensions.size());
    createInfo.ppEnabledExtensionNames =
        enabledExtensions.data();
    createInfo.pEnabledFeatures =
        &enabledFeatures;

    const VkResult result =
        vkCreateDevice(
            physicalDevice_,
            &createInfo,
            nullptr,
            &device_);

    if (!ok(result)) {
        logError("vkCreateDevice failed");
        return false;
    }

    vkGetDeviceQueue(
        device_,
        graphicsQueueFamily_,
        0,
        &graphicsQueue_);

    if (graphicsQueue_ == VK_NULL_HANDLE) {
        logError("vkGetDeviceQueue returned null");
        return false;
    }

    SwappyVk_setQueueFamilyIndex(
        device_,
        graphicsQueue_,
        graphicsQueueFamily_);

    return true;
}

bool VulkanClearRenderer::chooseSurfaceFormat(
    VkSurfaceFormatKHR& out) const noexcept {
    std::uint32_t count = 0;

    VkResult result =
        vkGetPhysicalDeviceSurfaceFormatsKHR(
            physicalDevice_,
            surface_,
            &count,
            nullptr);

    if (!ok(result) || count == 0) {
        return false;
    }

    std::vector<VkSurfaceFormatKHR> formats(count);

    result =
        vkGetPhysicalDeviceSurfaceFormatsKHR(
            physicalDevice_,
            surface_,
            &count,
            formats.data());

    if (!ok(result)) {
        return false;
    }

    for (const auto& format : formats) {
        if (format.format ==
                VK_FORMAT_R8G8B8A8_SRGB &&
            format.colorSpace ==
                VK_COLOR_SPACE_SRGB_NONLINEAR_KHR) {
            out = format;
            return true;
        }
    }

    for (const auto& format : formats) {
        if (format.format ==
                VK_FORMAT_B8G8R8A8_SRGB &&
            format.colorSpace ==
                VK_COLOR_SPACE_SRGB_NONLINEAR_KHR) {
            out = format;
            return true;
        }
    }

    out = formats.front();
    return true;
}

bool VulkanClearRenderer::chooseDepthFormat(
    VkFormat& out) const noexcept {
    constexpr std::array<VkFormat, 3> candidates{
        VK_FORMAT_D32_SFLOAT,
        VK_FORMAT_D24_UNORM_S8_UINT,
        VK_FORMAT_D16_UNORM,
    };

    for (const auto format : candidates) {
        VkFormatProperties properties{};

        vkGetPhysicalDeviceFormatProperties(
            physicalDevice_,
            format,
            &properties);

        if ((properties.optimalTilingFeatures &
             VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT) != 0) {
            out = format;
            return true;
        }
    }

    return false;
}

bool VulkanClearRenderer::findMemoryType(
    std::uint32_t typeBits,
    VkMemoryPropertyFlags required,
    std::uint32_t& outIndex) const noexcept {
    VkPhysicalDeviceMemoryProperties memoryProperties{};

    vkGetPhysicalDeviceMemoryProperties(
        physicalDevice_,
        &memoryProperties);

    for (std::uint32_t i = 0;
         i < memoryProperties.memoryTypeCount;
         ++i) {
        const bool allowed =
            (typeBits & (1U << i)) != 0;

        const bool matches =
            (memoryProperties.memoryTypes[i].propertyFlags &
             required) == required;

        if (allowed && matches) {
            outIndex = i;
            return true;
        }
    }

    return false;
}

bool VulkanClearRenderer::createSwapchain() noexcept {
    VkSurfaceCapabilitiesKHR caps{};

    if (!ok(
            vkGetPhysicalDeviceSurfaceCapabilitiesKHR(
                physicalDevice_,
                surface_,
                &caps))) {
        logError("surface capability query failed");
        return false;
    }

    if ((caps.supportedUsageFlags &
         VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT) == 0) {
        logError(
            "surface does not support color attachment usage");
        return false;
    }

    VkSurfaceFormatKHR surfaceFormat{};

    if (!chooseSurfaceFormat(surfaceFormat)) {
        logError("No usable surface format");
        return false;
    }

    const int nativeWindowWidth =
        std::max(
            1,
            ANativeWindow_getWidth(window_));
    const int nativeWindowHeight =
        std::max(
            1,
            ANativeWindow_getHeight(window_));

    VkExtent2D extent = caps.currentExtent;

    if (extent.width ==
        std::numeric_limits<std::uint32_t>::max()) {
        const auto width =
            static_cast<std::uint32_t>(
                nativeWindowWidth);

        const auto height =
            static_cast<std::uint32_t>(
                nativeWindowHeight);

        extent.width =
            std::clamp(
                width,
                caps.minImageExtent.width,
                caps.maxImageExtent.width);

        extent.height =
            std::clamp(
                height,
                caps.minImageExtent.height,
                caps.maxImageExtent.height);
    }

    std::uint32_t imageCount =
        caps.minImageCount + 1U;

    if (caps.maxImageCount > 0) {
        imageCount =
            std::min(
                imageCount,
                caps.maxImageCount);
    }

    VkSwapchainCreateInfoKHR createInfo{
        VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR
    };
    createInfo.surface = surface_;
    createInfo.minImageCount = imageCount;
    createInfo.imageFormat =
        surfaceFormat.format;
    createInfo.imageColorSpace =
        surfaceFormat.colorSpace;
    createInfo.imageExtent = extent;
    createInfo.imageArrayLayers = 1;
    createInfo.imageUsage =
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    createInfo.imageSharingMode =
        VK_SHARING_MODE_EXCLUSIVE;

    // Xziel currently renders world + HUD in the surface's logical
    // orientation and does not pre-rotate clip space for Android's
    // VkSurfaceTransformKHR. Advertising currentTransform here told SurfaceFlinger
    // the rotation was already baked into the image, producing a 90-degree
    // sideways frame on landscape devices whose natural orientation is
    // portrait. Prefer IDENTITY so Android owns the final display rotation.
    // If a rare surface cannot accept identity, keep the platform transform
    // rather than creating an invalid swapchain; the log below makes that
    // fallback explicit for follow-up shader pre-rotation support.
    VkSurfaceTransformFlagBitsKHR chosenPreTransform =
        caps.currentTransform;

    if ((caps.supportedTransforms &
         VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR) != 0U) {
        chosenPreTransform =
            VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
    }

    createInfo.preTransform =
        chosenPreTransform;
    createInfo.compositeAlpha =
        chooseCompositeAlpha(
            caps.supportedCompositeAlpha);
    createInfo.presentMode =
        VK_PRESENT_MODE_FIFO_KHR;
    createInfo.clipped = VK_TRUE;

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_VULKAN_SURFACE_ROTATION current=%u supported=0x%x chosen=%u extent=%ux%u window=%dx%d",
        static_cast<unsigned int>(
            caps.currentTransform),
        static_cast<unsigned int>(
            caps.supportedTransforms),
        static_cast<unsigned int>(
            chosenPreTransform),
        extent.width,
        extent.height,
        nativeWindowWidth,
        nativeWindowHeight);

    const VkResult result =
        vkCreateSwapchainKHR(
            device_,
            &createInfo,
            nullptr,
            &swapchain_);

    if (!ok(result)) {
        logError("vkCreateSwapchainKHR failed");
        return false;
    }

    swapchainFormat_ =
        surfaceFormat.format;
    swapchainExtent_ =
        extent;
    updateSceneExtent(
        activeRenderScale_);

    std::uint32_t actualCount = 0;

    if (!ok(
            vkGetSwapchainImagesKHR(
                device_,
                swapchain_,
                &actualCount,
                nullptr)) ||
        actualCount == 0) {
        logError("swapchain image count failed");
        return false;
    }

    swapchainImages_.resize(actualCount);

    if (!ok(
            vkGetSwapchainImagesKHR(
                device_,
                swapchain_,
                &actualCount,
                swapchainImages_.data()))) {
        logError("swapchain image list failed");
        return false;
    }

    imageFences_.assign(
        swapchainImages_.size(),
        VK_NULL_HANDLE);

    // Do not initialize Swappy inside swapchain creation. On some Android
    // devices (and SwiftShader CI) Swappy's refresh-cycle bootstrap can block
    // the native GameActivity thread before the first frame, which Android
    // surfaces as an ANR/"app isn't responding". FIFO present remains a safe
    // baseline; frame pacing can be enabled later after first-frame health is
    // established without making startup depend on the Java choreographer.
    swappyInitialized_ = false;
    framePacingAttempted_ = false;
    refreshDurationNs_ = 0;
    requestedSwapIntervalNs_ = 0;

    return true;
}

bool VulkanClearRenderer::initializeFramePacing() noexcept {
    swappyInitialized_ = false;
    refreshDurationNs_ = 0;
    requestedSwapIntervalNs_ = 0;

    if (jniEnv_ == nullptr ||
        javaActivity_ == nullptr ||
        physicalDevice_ == VK_NULL_HANDLE ||
        device_ == VK_NULL_HANDLE ||
        swapchain_ == VK_NULL_HANDLE ||
        window_ == nullptr) {
        logInfo("Swappy unavailable; using direct Vulkan present");
        return false;
    }

    const bool initialized =
        SwappyVk_initAndGetRefreshCycleDuration(
            jniEnv_,
            javaActivity_,
            physicalDevice_,
            device_,
            swapchain_,
            &refreshDurationNs_);

    if (!initialized ||
        refreshDurationNs_ == 0) {
        logInfo("Swappy init failed; using direct Vulkan present");
        refreshDurationNs_ = 0;
        return false;
    }

    SwappyVk_setWindow(
        device_,
        swapchain_,
        window_);

    SwappyVk_setAutoSwapInterval(true);
    SwappyVk_setAutoPipelineMode(true);

    // Begin at the native display cadence. Swappy may adapt the interval when
    // sustained frame cost requires it. RuntimePolicy will later choose
    // deliberate 60/90/120 targets.
    const std::uint64_t initialInterval =
        preferredFrameRate_ > 0.0f
        ? static_cast<std::uint64_t>(
              std::llround(
                  1000000000.0 /
                  static_cast<double>(
                      preferredFrameRate_)))
        : refreshDurationNs_;

    requestedSwapIntervalNs_ =
        std::max(
            initialInterval,
            refreshDurationNs_);

    SwappyVk_setSwapIntervalNS(
        device_,
        swapchain_,
        requestedSwapIntervalNs_);

    swappyInitialized_ = true;
    logInfo("XZIEL_SWAPPY_READY");
    return true;
}

bool VulkanClearRenderer::createRenderPass() noexcept {
    if (!chooseDepthFormat(depthFormat_)) {
        logError("No supported depth attachment format");
        return false;
    }

    const bool useMsaa =
        preferredSceneMsaa_ !=
        VK_SAMPLE_COUNT_1_BIT;

    VkAttachmentDescription color{};
    color.format = swapchainFormat_;
    color.samples =
        useMsaa
        ? preferredSceneMsaa_
        : VK_SAMPLE_COUNT_1_BIT;
    color.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    color.storeOp =
        useMsaa
        ? VK_ATTACHMENT_STORE_OP_DONT_CARE
        : VK_ATTACHMENT_STORE_OP_STORE;
    color.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    color.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    color.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    color.finalLayout =
        useMsaa
        ? VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL
        : VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;

    VkAttachmentDescription depth{};
    depth.format = depthFormat_;
    depth.samples = preferredSceneMsaa_;
    depth.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    depth.storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depth.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    depth.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depth.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    depth.finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    VkAttachmentDescription resolve{};
    resolve.format = swapchainFormat_;
    resolve.samples = VK_SAMPLE_COUNT_1_BIT;
    resolve.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    resolve.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    resolve.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    resolve.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    resolve.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    resolve.finalLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;

    const std::array<VkAttachmentDescription, 3> attachments{
        color,
        depth,
        resolve,
    };

    VkAttachmentReference colorReference{};
    colorReference.attachment = 0U;
    colorReference.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

    VkAttachmentReference depthReference{};
    depthReference.attachment = 1U;
    depthReference.layout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    VkAttachmentReference resolveReference{};
    resolveReference.attachment = 2U;
    resolveReference.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

    VkSubpassDescription subpass{};
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = 1U;
    subpass.pColorAttachments = &colorReference;
    subpass.pDepthStencilAttachment = &depthReference;
    subpass.pResolveAttachments =
        useMsaa
        ? &resolveReference
        : nullptr;

    std::array<VkSubpassDependency, 2> dependencies{};

    dependencies[0].srcSubpass = VK_SUBPASS_EXTERNAL;
    dependencies[0].dstSubpass = 0U;
    dependencies[0].srcStageMask =
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT |
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT |
        VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dependencies[0].dstStageMask =
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT |
        VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dependencies[0].srcAccessMask = VK_ACCESS_SHADER_READ_BIT;
    dependencies[0].dstAccessMask =
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT |
        VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;

    dependencies[1].srcSubpass = 0U;
    dependencies[1].dstSubpass = VK_SUBPASS_EXTERNAL;
    dependencies[1].srcStageMask =
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dependencies[1].dstStageMask =
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
    dependencies[1].srcAccessMask =
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    dependencies[1].dstAccessMask =
        VK_ACCESS_SHADER_READ_BIT;

    VkRenderPassCreateInfo createInfo{
        VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO
    };
    createInfo.attachmentCount =
        useMsaa
        ? 3U
        : 2U;
    createInfo.pAttachments = attachments.data();
    createInfo.subpassCount = 1U;
    createInfo.pSubpasses = &subpass;
    createInfo.dependencyCount =
        static_cast<std::uint32_t>(dependencies.size());
    createInfo.pDependencies = dependencies.data();

    const VkResult result =
        vkCreateRenderPass(
            device_,
            &createInfo,
            nullptr,
            &renderPass_);

    if (!ok(result)) {
        logError("vkCreateRenderPass world failed");
        return false;
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_SCENE_MSAA samples=%u",
        static_cast<unsigned int>(
            preferredSceneMsaa_));

    return true;
}

bool VulkanClearRenderer::createUiRenderPass() noexcept {
    VkAttachmentDescription color{};
    color.format = swapchainFormat_;
    color.samples = VK_SAMPLE_COUNT_1_BIT;
    // The pass starts with an opaque fullscreen scene composite that writes
    // every swapchain pixel, so clearing the attachment first is redundant.
    color.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    color.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    color.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    color.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    color.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    color.finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;

    VkAttachmentReference colorReference{};
    colorReference.attachment = 0U;
    colorReference.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

    VkSubpassDescription subpass{};
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = 1U;
    subpass.pColorAttachments = &colorReference;

    VkSubpassDependency dependency{};
    dependency.srcSubpass = VK_SUBPASS_EXTERNAL;
    dependency.dstSubpass = 0U;
    dependency.srcStageMask =
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dependency.dstStageMask =
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dependency.srcAccessMask = 0U;
    dependency.dstAccessMask =
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;

    VkRenderPassCreateInfo info{
        VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO
    };
    info.attachmentCount = 1U;
    info.pAttachments = &color;
    info.subpassCount = 1U;
    info.pSubpasses = &subpass;
    info.dependencyCount = 1U;
    info.pDependencies = &dependency;

    if (!ok(
            vkCreateRenderPass(
                device_,
                &info,
                nullptr,
                &uiRenderPass_))) {
        logError("vkCreateRenderPass native UI failed");
        return false;
    }

    return true;
}

bool VulkanClearRenderer::createShaderModuleFromAsset(
    const char* assetPath,
    VkShaderModule& outModule) noexcept {
    outModule = VK_NULL_HANDLE;

    if (assetManager_ == nullptr ||
        assetPath == nullptr ||
        device_ == VK_NULL_HANDLE) {
        return false;
    }

    AAsset* asset =
        AAssetManager_open(
            assetManager_,
            assetPath,
            AASSET_MODE_BUFFER);

    if (asset == nullptr) {
        logError("Failed to open SPIR-V shader asset");
        return false;
    }

    const off_t length =
        AAsset_getLength(asset);

    if (length <= 0 ||
        (length % 4) != 0) {
        AAsset_close(asset);
        logError("Invalid SPIR-V shader asset size");
        return false;
    }

    std::vector<std::uint32_t> words(
        static_cast<std::size_t>(length) / 4U);

    const int bytesRead =
        AAsset_read(
            asset,
            words.data(),
            static_cast<std::size_t>(length));

    AAsset_close(asset);

    if (bytesRead < 0 ||
        static_cast<off_t>(bytesRead) != length) {
        logError("Failed reading complete SPIR-V shader asset");
        return false;
    }

    VkShaderModuleCreateInfo createInfo{
        VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO
    };
    createInfo.codeSize =
        static_cast<std::size_t>(length);
    createInfo.pCode =
        words.data();

    const VkResult result =
        vkCreateShaderModule(
            device_,
            &createInfo,
            nullptr,
            &outModule);

    if (!ok(result)) {
        logError("vkCreateShaderModule failed");
        outModule = VK_NULL_HANDLE;
        return false;
    }

    return true;
}

bool VulkanClearRenderer::createGraphicsPipeline() noexcept {
    VkShaderModule vertex =
        VK_NULL_HANDLE;
    VkShaderModule fragment =
        VK_NULL_HANDLE;

    if (!createShaderModuleFromAsset(
            "shaders/xziel_first.vert.spv",
            vertex) ||
        !createShaderModuleFromAsset(
            "shaders/xziel_first.frag.spv",
            fragment)) {
        if (vertex != VK_NULL_HANDLE) {
            vkDestroyShaderModule(
                device_,
                vertex,
                nullptr);
        }

        if (fragment != VK_NULL_HANDLE) {
            vkDestroyShaderModule(
                device_,
                fragment,
                nullptr);
        }

        return false;
    }

    const std::array<VkPipelineShaderStageCreateInfo, 2>
        stages{{
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0,
                VK_SHADER_STAGE_VERTEX_BIT,
                vertex,
                "main",
                nullptr,
            },
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0,
                VK_SHADER_STAGE_FRAGMENT_BIT,
                fragment,
                "main",
                nullptr,
            },
        }};

    VkPipelineVertexInputStateCreateInfo vertexInput{
        VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO
    };

    VkPipelineInputAssemblyStateCreateInfo inputAssembly{
        VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO
    };
    inputAssembly.topology =
        VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    inputAssembly.primitiveRestartEnable =
        VK_FALSE;

    VkViewport viewport{};
    viewport.x = 0.0f;
    viewport.y = 0.0f;
    viewport.width =
        static_cast<float>(
            swapchainExtent_.width);
    viewport.height =
        static_cast<float>(
            swapchainExtent_.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;

    VkRect2D scissor{};
    scissor.offset = {0, 0};
    scissor.extent =
        swapchainExtent_;

    VkPipelineViewportStateCreateInfo viewportState{
        VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO
    };
    viewportState.viewportCount = 1;
    viewportState.pViewports =
        &viewport;
    viewportState.scissorCount = 1;
    viewportState.pScissors =
        &scissor;

    VkPipelineRasterizationStateCreateInfo raster{
        VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO
    };
    raster.depthClampEnable =
        VK_FALSE;
    raster.rasterizerDiscardEnable =
        VK_FALSE;
    raster.polygonMode =
        VK_POLYGON_MODE_FILL;
    raster.cullMode =
        VK_CULL_MODE_NONE;
    raster.frontFace =
        VK_FRONT_FACE_COUNTER_CLOCKWISE;
    raster.depthBiasEnable =
        VK_FALSE;
    raster.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo multisample{
        VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO
    };
    multisample.rasterizationSamples =
        preferredSceneMsaa_;
    multisample.sampleShadingEnable =
        VK_FALSE;

    VkPipelineDepthStencilStateCreateInfo depthStencil{
        VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO
    };
    depthStencil.depthTestEnable =
        VK_TRUE;
    depthStencil.depthWriteEnable =
        VK_TRUE;
    depthStencil.depthCompareOp =
        VK_COMPARE_OP_LESS_OR_EQUAL;
    depthStencil.depthBoundsTestEnable =
        VK_FALSE;
    depthStencil.stencilTestEnable =
        VK_FALSE;

    VkPipelineColorBlendAttachmentState colorAttachment{};
    colorAttachment.blendEnable =
        VK_FALSE;
    colorAttachment.colorWriteMask =
        VK_COLOR_COMPONENT_R_BIT |
        VK_COLOR_COMPONENT_G_BIT |
        VK_COLOR_COMPONENT_B_BIT |
        VK_COLOR_COMPONENT_A_BIT;

    VkPipelineColorBlendStateCreateInfo colorBlend{
        VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO
    };
    colorBlend.logicOpEnable =
        VK_FALSE;
    colorBlend.attachmentCount = 1;
    colorBlend.pAttachments =
        &colorAttachment;

    VkDescriptorSetLayoutBinding reflectionBinding{};
    reflectionBinding.binding = 0;
    reflectionBinding.descriptorType =
        VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    reflectionBinding.descriptorCount = 1;
    reflectionBinding.stageFlags =
        VK_SHADER_STAGE_FRAGMENT_BIT;

    VkDescriptorSetLayoutCreateInfo descriptorLayoutInfo{
        VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO
    };
    descriptorLayoutInfo.bindingCount = 1;
    descriptorLayoutInfo.pBindings = &reflectionBinding;

    if (!ok(
            vkCreateDescriptorSetLayout(
                device_,
                &descriptorLayoutInfo,
                nullptr,
                &reflectionDescriptorSetLayout_))) {
        vkDestroyShaderModule(device_, fragment, nullptr);
        vkDestroyShaderModule(device_, vertex, nullptr);
        logError("vkCreateDescriptorSetLayout reflection failed");
        return false;
    }

    VkPushConstantRange pushRange{};
    pushRange.stageFlags =
        VK_SHADER_STAGE_VERTEX_BIT |
        VK_SHADER_STAGE_FRAGMENT_BIT;
    pushRange.offset = 0;
    pushRange.size =
        static_cast<std::uint32_t>(
            sizeof(PushConstants));

    VkPipelineLayoutCreateInfo layoutInfo{
        VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO
    };
    layoutInfo.setLayoutCount = 1;
    layoutInfo.pSetLayouts =
        &reflectionDescriptorSetLayout_;
    layoutInfo.pushConstantRangeCount = 1;
    layoutInfo.pPushConstantRanges =
        &pushRange;

    VkResult result =
        vkCreatePipelineLayout(
            device_,
            &layoutInfo,
            nullptr,
            &pipelineLayout_);

    if (!ok(result)) {
        vkDestroyShaderModule(
            device_,
            fragment,
            nullptr);
        vkDestroyShaderModule(
            device_,
            vertex,
            nullptr);
        logError("vkCreatePipelineLayout failed");
        return false;
    }

    constexpr std::array<VkDynamicState, 2> dynamicStates{{
        VK_DYNAMIC_STATE_VIEWPORT,
        VK_DYNAMIC_STATE_SCISSOR,
    }};

    VkPipelineDynamicStateCreateInfo dynamicState{
        VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO
    };
    dynamicState.dynamicStateCount =
        static_cast<std::uint32_t>(dynamicStates.size());
    dynamicState.pDynamicStates = dynamicStates.data();

    VkGraphicsPipelineCreateInfo pipelineInfo{
        VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO
    };
    pipelineInfo.stageCount =
        static_cast<std::uint32_t>(
            stages.size());
    pipelineInfo.pStages =
        stages.data();
    pipelineInfo.pVertexInputState =
        &vertexInput;
    pipelineInfo.pInputAssemblyState =
        &inputAssembly;
    pipelineInfo.pViewportState =
        &viewportState;
    pipelineInfo.pRasterizationState =
        &raster;
    pipelineInfo.pMultisampleState =
        &multisample;
    pipelineInfo.pDepthStencilState =
        &depthStencil;
    pipelineInfo.pColorBlendState =
        &colorBlend;
    pipelineInfo.pDynamicState =
        &dynamicState;
    pipelineInfo.layout =
        pipelineLayout_;
    pipelineInfo.renderPass =
        renderPass_;
    pipelineInfo.subpass = 0;

    result =
        vkCreateGraphicsPipelines(
            device_,
            VK_NULL_HANDLE,
            1,
            &pipelineInfo,
            nullptr,
            &graphicsPipeline_);

    vkDestroyShaderModule(
        device_,
        fragment,
        nullptr);
    vkDestroyShaderModule(
        device_,
        vertex,
        nullptr);

    if (!ok(result)) {
        logError("vkCreateGraphicsPipelines failed");

        if (pipelineLayout_ != VK_NULL_HANDLE) {
            vkDestroyPipelineLayout(
                device_,
                pipelineLayout_,
                nullptr);
            pipelineLayout_ =
                VK_NULL_HANDLE;
        }

        graphicsPipeline_ =
            VK_NULL_HANDLE;
        return false;
    }

    logInfo("XZIEL_3D_PIPELINE_READY");
    return true;
}

bool VulkanClearRenderer::createSceneCompositePipeline() noexcept {
    VkShaderModule vertex = VK_NULL_HANDLE;
    VkShaderModule fragment = VK_NULL_HANDLE;

    if (!createShaderModuleFromAsset(
            "shaders/xziel_scene_composite.vert.spv",
            vertex) ||
        !createShaderModuleFromAsset(
            "shaders/xziel_scene_composite.frag.spv",
            fragment)) {
        if (vertex != VK_NULL_HANDLE) {
            vkDestroyShaderModule(device_, vertex, nullptr);
        }
        if (fragment != VK_NULL_HANDLE) {
            vkDestroyShaderModule(device_, fragment, nullptr);
        }
        return false;
    }

    VkDescriptorSetLayoutBinding sceneBinding{};
    sceneBinding.binding = 0U;
    sceneBinding.descriptorType =
        VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    sceneBinding.descriptorCount = 1U;
    sceneBinding.stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    VkDescriptorSetLayoutCreateInfo descriptorInfo{
        VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO
    };
    descriptorInfo.bindingCount = 1U;
    descriptorInfo.pBindings = &sceneBinding;

    if (!ok(
            vkCreateDescriptorSetLayout(
                device_,
                &descriptorInfo,
                nullptr,
                &sceneCompositeDescriptorSetLayout_))) {
        vkDestroyShaderModule(device_, fragment, nullptr);
        vkDestroyShaderModule(device_, vertex, nullptr);
        logError("scene composite descriptor layout failed");
        return false;
    }

    VkSamplerCreateInfo samplerInfo{
        VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO
    };
    samplerInfo.magFilter = VK_FILTER_LINEAR;
    samplerInfo.minFilter = VK_FILTER_LINEAR;
    samplerInfo.mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST;
    samplerInfo.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.minLod = 0.0f;
    samplerInfo.maxLod = 0.0f;

    if (!ok(
            vkCreateSampler(
                device_,
                &samplerInfo,
                nullptr,
                &sceneCompositeSampler_))) {
        vkDestroyShaderModule(device_, fragment, nullptr);
        vkDestroyShaderModule(device_, vertex, nullptr);
        logError("scene composite sampler failed");
        return false;
    }

    VkPipelineLayoutCreateInfo layoutInfo{
        VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO
    };
    layoutInfo.setLayoutCount = 1U;
    layoutInfo.pSetLayouts =
        &sceneCompositeDescriptorSetLayout_;

    if (!ok(
            vkCreatePipelineLayout(
                device_,
                &layoutInfo,
                nullptr,
                &sceneCompositePipelineLayout_))) {
        vkDestroyShaderModule(device_, fragment, nullptr);
        vkDestroyShaderModule(device_, vertex, nullptr);
        logError("scene composite pipeline layout failed");
        return false;
    }

    const std::array<VkPipelineShaderStageCreateInfo, 2> stages{{
        {
            VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            nullptr,
            0,
            VK_SHADER_STAGE_VERTEX_BIT,
            vertex,
            "main",
            nullptr,
        },
        {
            VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            nullptr,
            0,
            VK_SHADER_STAGE_FRAGMENT_BIT,
            fragment,
            "main",
            nullptr,
        },
    }};

    VkPipelineVertexInputStateCreateInfo vertexInput{
        VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO
    };

    VkPipelineInputAssemblyStateCreateInfo inputAssembly{
        VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO
    };
    inputAssembly.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;

    VkViewport viewport{};
    viewport.width =
        static_cast<float>(swapchainExtent_.width);
    viewport.height =
        static_cast<float>(swapchainExtent_.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;

    VkRect2D scissor{};
    scissor.extent = swapchainExtent_;

    VkPipelineViewportStateCreateInfo viewportState{
        VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO
    };
    viewportState.viewportCount = 1U;
    viewportState.pViewports = &viewport;
    viewportState.scissorCount = 1U;
    viewportState.pScissors = &scissor;

    VkPipelineRasterizationStateCreateInfo raster{
        VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO
    };
    raster.polygonMode = VK_POLYGON_MODE_FILL;
    raster.cullMode = VK_CULL_MODE_NONE;
    raster.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE;
    raster.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo multisample{
        VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO
    };
    multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

    VkPipelineColorBlendAttachmentState colorAttachment{};
    colorAttachment.colorWriteMask =
        VK_COLOR_COMPONENT_R_BIT |
        VK_COLOR_COMPONENT_G_BIT |
        VK_COLOR_COMPONENT_B_BIT |
        VK_COLOR_COMPONENT_A_BIT;

    VkPipelineColorBlendStateCreateInfo colorBlend{
        VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO
    };
    colorBlend.attachmentCount = 1U;
    colorBlend.pAttachments = &colorAttachment;

    VkGraphicsPipelineCreateInfo pipelineInfo{
        VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO
    };
    pipelineInfo.stageCount =
        static_cast<std::uint32_t>(stages.size());
    pipelineInfo.pStages = stages.data();
    pipelineInfo.pVertexInputState = &vertexInput;
    pipelineInfo.pInputAssemblyState = &inputAssembly;
    pipelineInfo.pViewportState = &viewportState;
    pipelineInfo.pRasterizationState = &raster;
    pipelineInfo.pMultisampleState = &multisample;
    pipelineInfo.pColorBlendState = &colorBlend;
    pipelineInfo.layout = sceneCompositePipelineLayout_;
    pipelineInfo.renderPass = uiRenderPass_;
    pipelineInfo.subpass = 0U;

    const VkResult result =
        vkCreateGraphicsPipelines(
            device_,
            VK_NULL_HANDLE,
            1U,
            &pipelineInfo,
            nullptr,
            &sceneCompositePipeline_);

    vkDestroyShaderModule(device_, fragment, nullptr);
    vkDestroyShaderModule(device_, vertex, nullptr);

    if (!ok(result)) {
        logError("scene composite graphics pipeline failed");
        return false;
    }

    logInfo("XZIEL_SCENE_COMPOSITE_READY");
    return true;
}

bool VulkanClearRenderer::createUiPipeline() noexcept {
    VkShaderModule vertex =
        VK_NULL_HANDLE;
    VkShaderModule fragment =
        VK_NULL_HANDLE;

    if (!createShaderModuleFromAsset(
            "shaders/xziel_ui.vert.spv",
            vertex) ||
        !createShaderModuleFromAsset(
            "shaders/xziel_ui.frag.spv",
            fragment)) {
        if (vertex != VK_NULL_HANDLE) {
            vkDestroyShaderModule(
                device_,
                vertex,
                nullptr);
        }

        if (fragment != VK_NULL_HANDLE) {
            vkDestroyShaderModule(
                device_,
                fragment,
                nullptr);
        }

        return false;
    }

    const std::array<VkPipelineShaderStageCreateInfo, 2>
        stages{{
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0,
                VK_SHADER_STAGE_VERTEX_BIT,
                vertex,
                "main",
                nullptr,
            },
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0,
                VK_SHADER_STAGE_FRAGMENT_BIT,
                fragment,
                "main",
                nullptr,
            },
        }};

    VkPipelineVertexInputStateCreateInfo vertexInput{
        VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO
    };

    VkPipelineInputAssemblyStateCreateInfo inputAssembly{
        VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO
    };
    inputAssembly.topology =
        VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    inputAssembly.primitiveRestartEnable =
        VK_FALSE;

    VkViewport viewport{};
    viewport.x = 0.0f;
    viewport.y = 0.0f;
    viewport.width =
        static_cast<float>(
            swapchainExtent_.width);
    viewport.height =
        static_cast<float>(
            swapchainExtent_.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;

    VkRect2D scissor{};
    scissor.offset = {0, 0};
    scissor.extent =
        swapchainExtent_;

    VkPipelineViewportStateCreateInfo viewportState{
        VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO
    };
    viewportState.viewportCount = 1;
    viewportState.pViewports =
        &viewport;
    viewportState.scissorCount = 1;
    viewportState.pScissors =
        &scissor;

    VkPipelineRasterizationStateCreateInfo raster{
        VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO
    };
    raster.depthClampEnable =
        VK_FALSE;
    raster.rasterizerDiscardEnable =
        VK_FALSE;
    raster.polygonMode =
        VK_POLYGON_MODE_FILL;
    raster.cullMode =
        VK_CULL_MODE_NONE;
    raster.frontFace =
        VK_FRONT_FACE_COUNTER_CLOCKWISE;
    raster.depthBiasEnable =
        VK_FALSE;
    raster.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo multisample{
        VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO
    };
    multisample.rasterizationSamples =
        VK_SAMPLE_COUNT_1_BIT;
    multisample.sampleShadingEnable =
        VK_FALSE;

    VkPipelineDepthStencilStateCreateInfo depthStencil{
        VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO
    };
    depthStencil.depthTestEnable =
        VK_FALSE;
    depthStencil.depthWriteEnable =
        VK_FALSE;
    depthStencil.depthCompareOp =
        VK_COMPARE_OP_ALWAYS;
    depthStencil.depthBoundsTestEnable =
        VK_FALSE;
    depthStencil.stencilTestEnable =
        VK_FALSE;

    VkPipelineColorBlendAttachmentState colorAttachment{};
    colorAttachment.blendEnable =
        VK_TRUE;
    colorAttachment.srcColorBlendFactor =
        VK_BLEND_FACTOR_SRC_ALPHA;
    colorAttachment.dstColorBlendFactor =
        VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA;
    colorAttachment.colorBlendOp =
        VK_BLEND_OP_ADD;
    colorAttachment.srcAlphaBlendFactor =
        VK_BLEND_FACTOR_ONE;
    colorAttachment.dstAlphaBlendFactor =
        VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA;
    colorAttachment.alphaBlendOp =
        VK_BLEND_OP_ADD;
    colorAttachment.colorWriteMask =
        VK_COLOR_COMPONENT_R_BIT |
        VK_COLOR_COMPONENT_G_BIT |
        VK_COLOR_COMPONENT_B_BIT |
        VK_COLOR_COMPONENT_A_BIT;

    VkPipelineColorBlendStateCreateInfo colorBlend{
        VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO
    };
    colorBlend.logicOpEnable =
        VK_FALSE;
    colorBlend.attachmentCount = 1;
    colorBlend.pAttachments =
        &colorAttachment;

    VkPushConstantRange pushRange{};
    pushRange.stageFlags =
        VK_SHADER_STAGE_VERTEX_BIT |
        VK_SHADER_STAGE_FRAGMENT_BIT;
    pushRange.offset = 0;
    pushRange.size =
        static_cast<std::uint32_t>(
            sizeof(UiPushConstants));

    VkPipelineLayoutCreateInfo layoutInfo{
        VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO
    };
    layoutInfo.pushConstantRangeCount = 1;
    layoutInfo.pPushConstantRanges =
        &pushRange;

    VkResult result =
        vkCreatePipelineLayout(
            device_,
            &layoutInfo,
            nullptr,
            &uiPipelineLayout_);

    if (!ok(result)) {
        vkDestroyShaderModule(
            device_,
            fragment,
            nullptr);
        vkDestroyShaderModule(
            device_,
            vertex,
            nullptr);
        logError("vkCreatePipelineLayout UI failed");
        return false;
    }

    VkGraphicsPipelineCreateInfo pipelineInfo{
        VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO
    };
    pipelineInfo.stageCount =
        static_cast<std::uint32_t>(
            stages.size());
    pipelineInfo.pStages =
        stages.data();
    pipelineInfo.pVertexInputState =
        &vertexInput;
    pipelineInfo.pInputAssemblyState =
        &inputAssembly;
    pipelineInfo.pViewportState =
        &viewportState;
    pipelineInfo.pRasterizationState =
        &raster;
    pipelineInfo.pMultisampleState =
        &multisample;
    pipelineInfo.pDepthStencilState =
        &depthStencil;
    pipelineInfo.pColorBlendState =
        &colorBlend;
    pipelineInfo.layout =
        uiPipelineLayout_;
    pipelineInfo.renderPass =
        uiRenderPass_;
    pipelineInfo.subpass = 0;

    result =
        vkCreateGraphicsPipelines(
            device_,
            VK_NULL_HANDLE,
            1,
            &pipelineInfo,
            nullptr,
            &uiPipeline_);

    vkDestroyShaderModule(
        device_,
        fragment,
        nullptr);
    vkDestroyShaderModule(
        device_,
        vertex,
        nullptr);

    if (!ok(result)) {
        logError("vkCreateGraphicsPipelines UI failed");

        if (uiPipelineLayout_ != VK_NULL_HANDLE) {
            vkDestroyPipelineLayout(
                device_,
                uiPipelineLayout_,
                nullptr);
            uiPipelineLayout_ =
                VK_NULL_HANDLE;
        }

        uiPipeline_ =
            VK_NULL_HANDLE;
        return false;
    }

    VkShaderModule batchVertex = VK_NULL_HANDLE;
    VkShaderModule batchFragment = VK_NULL_HANDLE;

    if (!createShaderModuleFromAsset(
            "shaders/xziel_ui_batch.vert.spv",
            batchVertex) ||
        !createShaderModuleFromAsset(
            "shaders/xziel_ui_batch.frag.spv",
            batchFragment)) {
        if (batchVertex != VK_NULL_HANDLE) {
            vkDestroyShaderModule(device_, batchVertex, nullptr);
        }
        if (batchFragment != VK_NULL_HANDLE) {
            vkDestroyShaderModule(device_, batchFragment, nullptr);
        }
        logError("UI batch shader load failed");
        return false;
    }

    const std::array<VkPipelineShaderStageCreateInfo, 2>
        batchStages{{
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0,
                VK_SHADER_STAGE_VERTEX_BIT,
                batchVertex,
                "main",
                nullptr,
            },
            {
                VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                nullptr,
                0,
                VK_SHADER_STAGE_FRAGMENT_BIT,
                batchFragment,
                "main",
                nullptr,
            },
        }};

    VkVertexInputBindingDescription batchBinding{};
    batchBinding.binding = 0U;
    batchBinding.stride =
        static_cast<std::uint32_t>(
            sizeof(UiBatchVertex));
    batchBinding.inputRate =
        VK_VERTEX_INPUT_RATE_VERTEX;

    const std::array<VkVertexInputAttributeDescription, 4>
        batchAttributes{{
            {
                0U,
                0U,
                VK_FORMAT_R32G32_SFLOAT,
                static_cast<std::uint32_t>(
                    offsetof(UiBatchVertex, positionX)),
            },
            {
                1U,
                0U,
                VK_FORMAT_R32G32_SFLOAT,
                static_cast<std::uint32_t>(
                    offsetof(UiBatchVertex, localX)),
            },
            {
                2U,
                0U,
                VK_FORMAT_R32G32B32A32_SFLOAT,
                static_cast<std::uint32_t>(
                    offsetof(UiBatchVertex, colorR)),
            },
            {
                3U,
                0U,
                VK_FORMAT_R32G32_SFLOAT,
                static_cast<std::uint32_t>(
                    offsetof(UiBatchVertex, shape)),
            },
        }};

    VkPipelineVertexInputStateCreateInfo batchVertexInput{
        VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO
    };
    batchVertexInput.vertexBindingDescriptionCount = 1U;
    batchVertexInput.pVertexBindingDescriptions =
        &batchBinding;
    batchVertexInput.vertexAttributeDescriptionCount =
        static_cast<std::uint32_t>(
            batchAttributes.size());
    batchVertexInput.pVertexAttributeDescriptions =
        batchAttributes.data();

    VkGraphicsPipelineCreateInfo batchPipelineInfo =
        pipelineInfo;
    batchPipelineInfo.pStages =
        batchStages.data();
    batchPipelineInfo.pVertexInputState =
        &batchVertexInput;

    result =
        vkCreateGraphicsPipelines(
            device_,
            VK_NULL_HANDLE,
            1U,
            &batchPipelineInfo,
            nullptr,
            &uiBatchPipeline_);

    vkDestroyShaderModule(
        device_,
        batchFragment,
        nullptr);
    vkDestroyShaderModule(
        device_,
        batchVertex,
        nullptr);

    if (!ok(result)) {
        uiBatchPipeline_ = VK_NULL_HANDLE;
        logError("vkCreateGraphicsPipelines UI batch failed");
        return false;
    }

    logInfo("XZIEL_UI_PIPELINE_READY");
    logInfo("XZIEL_UI_BATCH_PIPELINE_READY");
    return true;
}

bool VulkanClearRenderer::createUiBatchResources() noexcept {
    if (uiBatchVertexBuffer_ != VK_NULL_HANDLE &&
        uiBatchVertexMemory_ != VK_NULL_HANDLE &&
        uiBatchMapped_ != nullptr) {
        return true;
    }

    destroyUiBatchResources();

    const VkDeviceSize frameBytes =
        static_cast<VkDeviceSize>(
            sizeof(UiBatchVertex)) *
        kUiBatchVerticesPerFrame;
    const VkDeviceSize totalBytes =
        frameBytes *
        kFramesInFlight;

    VkBufferCreateInfo bufferInfo{
        VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO
    };
    bufferInfo.size = totalBytes;
    bufferInfo.usage =
        VK_BUFFER_USAGE_VERTEX_BUFFER_BIT;
    bufferInfo.sharingMode =
        VK_SHARING_MODE_EXCLUSIVE;

    if (!ok(
            vkCreateBuffer(
                device_,
                &bufferInfo,
                nullptr,
                &uiBatchVertexBuffer_))) {
        logError("UI batch vertex buffer creation failed");
        return false;
    }

    VkMemoryRequirements requirements{};
    vkGetBufferMemoryRequirements(
        device_,
        uiBatchVertexBuffer_,
        &requirements);

    std::uint32_t memoryType = 0U;
    if (!findMemoryType(
            requirements.memoryTypeBits,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
            memoryType)) {
        logError("No host-visible memory for UI batch");
        destroyUiBatchResources();
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
                &uiBatchVertexMemory_)) ||
        !ok(
            vkBindBufferMemory(
                device_,
                uiBatchVertexBuffer_,
                uiBatchVertexMemory_,
                0U)) ||
        !ok(
            vkMapMemory(
                device_,
                uiBatchVertexMemory_,
                0U,
                VK_WHOLE_SIZE,
                0U,
                &uiBatchMapped_))) {
        logError("UI batch vertex memory setup failed");
        destroyUiBatchResources();
        return false;
    }

    std::memset(
        uiBatchMapped_,
        0,
        static_cast<std::size_t>(
            totalBytes));

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_UI_BATCH_BUFFER_READY bytes=%llu vertices_per_frame=%u",
        static_cast<unsigned long long>(
            totalBytes),
        kUiBatchVerticesPerFrame);
    return true;
}

void VulkanClearRenderer::destroyUiBatchResources() noexcept {
    if (device_ != VK_NULL_HANDLE &&
        uiBatchMapped_ != nullptr &&
        uiBatchVertexMemory_ != VK_NULL_HANDLE) {
        vkUnmapMemory(
            device_,
            uiBatchVertexMemory_);
    }
    uiBatchMapped_ = nullptr;

    if (device_ != VK_NULL_HANDLE &&
        uiBatchVertexBuffer_ != VK_NULL_HANDLE) {
        vkDestroyBuffer(
            device_,
            uiBatchVertexBuffer_,
            nullptr);
    }
    uiBatchVertexBuffer_ = VK_NULL_HANDLE;

    if (device_ != VK_NULL_HANDLE &&
        uiBatchVertexMemory_ != VK_NULL_HANDLE) {
        vkFreeMemory(
            device_,
            uiBatchVertexMemory_,
            nullptr);
    }
    uiBatchVertexMemory_ = VK_NULL_HANDLE;
}

bool VulkanClearRenderer::createImageViews() noexcept {
    imageViews_.assign(
        swapchainImages_.size(),
        VK_NULL_HANDLE);

    for (std::size_t i = 0;
         i < swapchainImages_.size();
         ++i) {
        VkImageViewCreateInfo view{
            VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
        };
        view.image =
            swapchainImages_[i];
        view.viewType =
            VK_IMAGE_VIEW_TYPE_2D;
        view.format =
            swapchainFormat_;
        view.components = {
            VK_COMPONENT_SWIZZLE_IDENTITY,
            VK_COMPONENT_SWIZZLE_IDENTITY,
            VK_COMPONENT_SWIZZLE_IDENTITY,
            VK_COMPONENT_SWIZZLE_IDENTITY,
        };
        view.subresourceRange.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        view.subresourceRange.baseMipLevel = 0;
        view.subresourceRange.levelCount = 1;
        view.subresourceRange.baseArrayLayer = 0;
        view.subresourceRange.layerCount = 1;

        if (!ok(
                vkCreateImageView(
                    device_,
                    &view,
                    nullptr,
                    &imageViews_[i]))) {
            logError("vkCreateImageView failed");
            return false;
        }
    }

    return true;
}

bool VulkanClearRenderer::createSceneColorResources() noexcept {
    sceneColorImages_.clear();
    sceneColorMemory_.clear();
    sceneColorViews_.clear();

    if (preferredSceneMsaa_ ==
        VK_SAMPLE_COUNT_1_BIT) {
        return true;
    }

    const std::size_t count =
        swapchainImages_.size();

    sceneColorImages_.assign(
        count,
        VK_NULL_HANDLE);
    sceneColorMemory_.assign(
        count,
        VK_NULL_HANDLE);
    sceneColorViews_.assign(
        count,
        VK_NULL_HANDLE);

    bool usedLazyTransientMemory = false;

    for (std::size_t i = 0U;
         i < count;
         ++i) {
        VkImageCreateInfo imageInfo{
            VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO
        };
        imageInfo.imageType =
            VK_IMAGE_TYPE_2D;
        imageInfo.format =
            swapchainFormat_;
        imageInfo.extent = {
            sceneExtent_.width,
            sceneExtent_.height,
            1U,
        };
        imageInfo.mipLevels = 1U;
        imageInfo.arrayLayers = 1U;
        imageInfo.samples =
            preferredSceneMsaa_;
        imageInfo.tiling =
            VK_IMAGE_TILING_OPTIMAL;
        imageInfo.usage =
            VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
            VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT;
        imageInfo.sharingMode =
            VK_SHARING_MODE_EXCLUSIVE;
        imageInfo.initialLayout =
            VK_IMAGE_LAYOUT_UNDEFINED;

        if (!ok(
                vkCreateImage(
                    device_,
                    &imageInfo,
                    nullptr,
                    &sceneColorImages_[i]))) {
            logError(
                "vkCreateImage transient scene color failed");
            return false;
        }

        VkMemoryRequirements requirements{};
        vkGetImageMemoryRequirements(
            device_,
            sceneColorImages_[i],
            &requirements);

        std::uint32_t memoryType = 0U;
        const bool lazyMemory =
            findMemoryType(
                requirements.memoryTypeBits,
                VK_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT,
                memoryType);

        if (!lazyMemory &&
            !findMemoryType(
                requirements.memoryTypeBits,
                VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                memoryType)) {
            logError(
                "No suitable memory for transient scene color");
            return false;
        }

        usedLazyTransientMemory =
            usedLazyTransientMemory ||
            lazyMemory;

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
                    &sceneColorMemory_[i])) ||
            !ok(
                vkBindImageMemory(
                    device_,
                    sceneColorImages_[i],
                    sceneColorMemory_[i],
                    0U))) {
            logError(
                "transient scene color allocation failed");
            return false;
        }

        VkImageViewCreateInfo view{
            VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
        };
        view.image =
            sceneColorImages_[i];
        view.viewType =
            VK_IMAGE_VIEW_TYPE_2D;
        view.format =
            swapchainFormat_;
        view.subresourceRange.aspectMask =
            VK_IMAGE_ASPECT_COLOR_BIT;
        view.subresourceRange.baseMipLevel = 0U;
        view.subresourceRange.levelCount = 1U;
        view.subresourceRange.baseArrayLayer = 0U;
        view.subresourceRange.layerCount = 1U;

        if (!ok(
                vkCreateImageView(
                    device_,
                    &view,
                    nullptr,
                    &sceneColorViews_[i]))) {
            logError(
                "transient scene color view failed");
            return false;
        }
    }

    logInfo(
        usedLazyTransientMemory
            ? "XZIEL_TRANSIENT_MSAA_COLOR_LAZY"
            : "XZIEL_TRANSIENT_MSAA_COLOR_DEVICE_LOCAL");

    return true;
}

bool VulkanClearRenderer::createSceneResolveResources() noexcept {
    sceneResolveImages_.clear();
    sceneResolveMemory_.clear();
    sceneResolveViews_.clear();

    const std::size_t count = swapchainImages_.size();

    sceneResolveImages_.assign(count, VK_NULL_HANDLE);
    sceneResolveMemory_.assign(count, VK_NULL_HANDLE);
    sceneResolveViews_.assign(count, VK_NULL_HANDLE);

    for (std::size_t i = 0U; i < count; ++i) {
        VkImageCreateInfo imageInfo{
            VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO
        };
        imageInfo.imageType = VK_IMAGE_TYPE_2D;
        imageInfo.format = swapchainFormat_;
        imageInfo.extent = {
            sceneExtent_.width,
            sceneExtent_.height,
            1U,
        };
        imageInfo.mipLevels = 1U;
        imageInfo.arrayLayers = 1U;
        imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
        imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
        imageInfo.usage =
            VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
            VK_IMAGE_USAGE_SAMPLED_BIT;
        imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;

        if (!ok(
                vkCreateImage(
                    device_,
                    &imageInfo,
                    nullptr,
                    &sceneResolveImages_[i]))) {
            logError("scene resolve image creation failed");
            return false;
        }

        VkMemoryRequirements requirements{};
        vkGetImageMemoryRequirements(
            device_,
            sceneResolveImages_[i],
            &requirements);

        std::uint32_t memoryType = 0U;
        if (!findMemoryType(
                requirements.memoryTypeBits,
                VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                memoryType)) {
            logError("no device-local memory for scene resolve");
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
                    &sceneResolveMemory_[i])) ||
            !ok(
                vkBindImageMemory(
                    device_,
                    sceneResolveImages_[i],
                    sceneResolveMemory_[i],
                    0U))) {
            logError("scene resolve allocation failed");
            return false;
        }

        VkImageViewCreateInfo view{
            VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
        };
        view.image = sceneResolveImages_[i];
        view.viewType = VK_IMAGE_VIEW_TYPE_2D;
        view.format = swapchainFormat_;
        view.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        view.subresourceRange.levelCount = 1U;
        view.subresourceRange.layerCount = 1U;

        if (!ok(
                vkCreateImageView(
                    device_,
                    &view,
                    nullptr,
                    &sceneResolveViews_[i]))) {
            logError("scene resolve view creation failed");
            return false;
        }
    }

    return true;
}

bool VulkanClearRenderer::createDepthResources() noexcept {
    const std::size_t count =
        swapchainImages_.size();

    depthImages_.assign(
        count,
        VK_NULL_HANDLE);
    depthMemory_.assign(
        count,
        VK_NULL_HANDLE);
    depthViews_.assign(
        count,
        VK_NULL_HANDLE);

    bool usedLazyTransientMemory = false;

    for (std::size_t i = 0;
         i < count;
         ++i) {
        VkImageCreateInfo imageInfo{
            VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO
        };
        imageInfo.imageType =
            VK_IMAGE_TYPE_2D;
        imageInfo.format =
            depthFormat_;
        imageInfo.extent = {
            sceneExtent_.width,
            sceneExtent_.height,
            1,
        };
        imageInfo.mipLevels = 1;
        imageInfo.arrayLayers = 1;
        imageInfo.samples =
            preferredSceneMsaa_;
        imageInfo.tiling =
            VK_IMAGE_TILING_OPTIMAL;
        // Depth is cleared every frame and discarded at the end of the
        // render pass. Mark it transient so tile-based mobile GPUs can keep
        // it on-chip instead of round-tripping it through external memory.
        imageInfo.usage =
            VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT |
            VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT;
        imageInfo.sharingMode =
            VK_SHARING_MODE_EXCLUSIVE;
        imageInfo.initialLayout =
            VK_IMAGE_LAYOUT_UNDEFINED;

        if (!ok(
                vkCreateImage(
                    device_,
                    &imageInfo,
                    nullptr,
                    &depthImages_[i]))) {
            logError("vkCreateImage depth failed");
            return false;
        }

        VkMemoryRequirements requirements{};

        vkGetImageMemoryRequirements(
            device_,
            depthImages_[i],
            &requirements);

        std::uint32_t memoryType = 0;

        const bool lazyMemory =
            findMemoryType(
                requirements.memoryTypeBits,
                VK_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT,
                memoryType);

        if (!lazyMemory &&
            !findMemoryType(
                requirements.memoryTypeBits,
                VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                memoryType)) {
            logError("No suitable memory for transient depth image");
            return false;
        }

        usedLazyTransientMemory =
            usedLazyTransientMemory ||
            lazyMemory;

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
                    &depthMemory_[i]))) {
            logError("vkAllocateMemory depth failed");
            return false;
        }

        if (!ok(
                vkBindImageMemory(
                    device_,
                    depthImages_[i],
                    depthMemory_[i],
                    0))) {
            logError("vkBindImageMemory depth failed");
            return false;
        }

        VkImageViewCreateInfo view{
            VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
        };
        view.image =
            depthImages_[i];
        view.viewType =
            VK_IMAGE_VIEW_TYPE_2D;
        view.format =
            depthFormat_;
        view.subresourceRange.aspectMask =
            VK_IMAGE_ASPECT_DEPTH_BIT;
        view.subresourceRange.baseMipLevel = 0;
        view.subresourceRange.levelCount = 1;
        view.subresourceRange.baseArrayLayer = 0;
        view.subresourceRange.layerCount = 1;

        if (!ok(
                vkCreateImageView(
                    device_,
                    &view,
                    nullptr,
                    &depthViews_[i]))) {
            logError("vkCreateImageView depth failed");
            return false;
        }
    }

    logInfo(
        usedLazyTransientMemory
            ? "XZIEL_TRANSIENT_DEPTH_LAZY"
            : "XZIEL_TRANSIENT_DEPTH_DEVICE_LOCAL");

    return true;
}

bool VulkanClearRenderer::createSceneCompositeDescriptors() noexcept {
    if (sceneCompositeSampler_ == VK_NULL_HANDLE ||
        sceneCompositeDescriptorSetLayout_ == VK_NULL_HANDLE ||
        sceneResolveViews_.empty()) {
        return false;
    }

    if (sceneCompositeDescriptorPool_ != VK_NULL_HANDLE) {
        vkDestroyDescriptorPool(
            device_,
            sceneCompositeDescriptorPool_,
            nullptr);
        sceneCompositeDescriptorPool_ = VK_NULL_HANDLE;
    }
    sceneCompositeDescriptorSets_.clear();

    VkDescriptorPoolSize poolSize{};
    poolSize.type = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    poolSize.descriptorCount =
        static_cast<std::uint32_t>(sceneResolveViews_.size());

    VkDescriptorPoolCreateInfo poolInfo{
        VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO
    };
    poolInfo.maxSets =
        static_cast<std::uint32_t>(sceneResolveViews_.size());
    poolInfo.poolSizeCount = 1U;
    poolInfo.pPoolSizes = &poolSize;

    if (!ok(
            vkCreateDescriptorPool(
                device_,
                &poolInfo,
                nullptr,
                &sceneCompositeDescriptorPool_))) {
        logError("scene composite descriptor pool failed");
        return false;
    }

    std::vector<VkDescriptorSetLayout> layouts(
        sceneResolveViews_.size(),
        sceneCompositeDescriptorSetLayout_);

    sceneCompositeDescriptorSets_.assign(
        sceneResolveViews_.size(),
        VK_NULL_HANDLE);

    VkDescriptorSetAllocateInfo allocation{
        VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO
    };
    allocation.descriptorPool = sceneCompositeDescriptorPool_;
    allocation.descriptorSetCount =
        static_cast<std::uint32_t>(layouts.size());
    allocation.pSetLayouts = layouts.data();

    if (!ok(
            vkAllocateDescriptorSets(
                device_,
                &allocation,
                sceneCompositeDescriptorSets_.data()))) {
        logError("scene composite descriptor allocation failed");
        return false;
    }

    for (std::size_t i = 0U;
         i < sceneCompositeDescriptorSets_.size();
         ++i) {
        VkDescriptorImageInfo image{};
        image.sampler = sceneCompositeSampler_;
        image.imageView = sceneResolveViews_[i];
        image.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;

        VkWriteDescriptorSet write{
            VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET
        };
        write.dstSet = sceneCompositeDescriptorSets_[i];
        write.dstBinding = 0U;
        write.descriptorCount = 1U;
        write.descriptorType =
            VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        write.pImageInfo = &image;

        vkUpdateDescriptorSets(
            device_,
            1U,
            &write,
            0U,
            nullptr);
    }

    return true;
}

bool VulkanClearRenderer::createReflectionFallbackResources() noexcept {
    if (device_ == VK_NULL_HANDLE || commandPool_ == VK_NULL_HANDLE ||
        reflectionDescriptorSetLayout_ == VK_NULL_HANDLE) {
        return false;
    }

    if (reflectionFallbackView_ != VK_NULL_HANDLE &&
        reflectionDescriptorSet_ != VK_NULL_HANDLE) {
        updateReflectionDescriptor(reflectionFallbackView_);
        reflectionHasValidContents_ = true;
        return true;
    }

    VkImageCreateInfo imageInfo{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.format = VK_FORMAT_R8G8B8A8_UNORM;
    imageInfo.extent = {1, 1, 1};
    imageInfo.mipLevels = 1;
    imageInfo.arrayLayers = 1;
    imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
    imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
    imageInfo.usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    if (!ok(vkCreateImage(device_, &imageInfo, nullptr, &reflectionFallbackImage_))) return false;

    VkMemoryRequirements requirements{};
    vkGetImageMemoryRequirements(device_, reflectionFallbackImage_, &requirements);
    std::uint32_t memoryType = 0;
    if (!findMemoryType(requirements.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, memoryType)) return false;
    VkMemoryAllocateInfo allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
    allocation.allocationSize = requirements.size;
    allocation.memoryTypeIndex = memoryType;
    if (!ok(vkAllocateMemory(device_, &allocation, nullptr, &reflectionFallbackMemory_)) ||
        !ok(vkBindImageMemory(device_, reflectionFallbackImage_, reflectionFallbackMemory_, 0))) return false;

    VkImageViewCreateInfo viewInfo{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
    viewInfo.image = reflectionFallbackImage_;
    viewInfo.viewType = VK_IMAGE_VIEW_TYPE_2D;
    viewInfo.format = VK_FORMAT_R8G8B8A8_UNORM;
    viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.levelCount = 1;
    viewInfo.subresourceRange.layerCount = 1;
    if (!ok(vkCreateImageView(device_, &viewInfo, nullptr, &reflectionFallbackView_))) return false;

    VkSamplerCreateInfo samplerInfo{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
    samplerInfo.magFilter = VK_FILTER_LINEAR;
    samplerInfo.minFilter = VK_FILTER_LINEAR;
    samplerInfo.mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST;
    samplerInfo.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.maxAnisotropy = 1.0f;
    if (!ok(vkCreateSampler(device_, &samplerInfo, nullptr, &reflectionSampler_))) return false;

    VkDescriptorPoolSize poolSize{};
    poolSize.type = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    poolSize.descriptorCount = 1;
    VkDescriptorPoolCreateInfo poolInfo{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
    poolInfo.maxSets = 1;
    poolInfo.poolSizeCount = 1;
    poolInfo.pPoolSizes = &poolSize;
    if (!ok(vkCreateDescriptorPool(device_, &poolInfo, nullptr, &reflectionDescriptorPool_))) return false;

    VkDescriptorSetAllocateInfo setInfo{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
    setInfo.descriptorPool = reflectionDescriptorPool_;
    setInfo.descriptorSetCount = 1;
    setInfo.pSetLayouts = &reflectionDescriptorSetLayout_;
    if (!ok(vkAllocateDescriptorSets(device_, &setInfo, &reflectionDescriptorSet_))) return false;

    VkCommandBufferAllocateInfo commandInfo{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
    commandInfo.commandPool = commandPool_;
    commandInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    commandInfo.commandBufferCount = 1;
    VkCommandBuffer command = VK_NULL_HANDLE;
    if (!ok(vkAllocateCommandBuffers(device_, &commandInfo, &command))) return false;
    VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    begin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    if (!ok(vkBeginCommandBuffer(command, &begin))) return false;

    VkImageMemoryBarrier toTransfer{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
    toTransfer.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    toTransfer.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    toTransfer.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    toTransfer.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    toTransfer.image = reflectionFallbackImage_;
    toTransfer.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    toTransfer.subresourceRange.levelCount = 1;
    toTransfer.subresourceRange.layerCount = 1;
    toTransfer.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, nullptr, 0, nullptr, 1, &toTransfer);

    VkClearColorValue clear{};
    clear.float32[0] = 0.008f; clear.float32[1] = 0.010f; clear.float32[2] = 0.016f; clear.float32[3] = 1.0f;
    VkImageSubresourceRange range{};
    range.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT; range.levelCount = 1; range.layerCount = 1;
    vkCmdClearColorImage(command, reflectionFallbackImage_, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &clear, 1, &range);

    VkImageMemoryBarrier toSample = toTransfer;
    toSample.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    toSample.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    toSample.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    toSample.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0, 0, nullptr, 0, nullptr, 1, &toSample);
    if (!ok(vkEndCommandBuffer(command))) return false;
    VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};
    submit.commandBufferCount = 1; submit.pCommandBuffers = &command;
    if (!ok(vkQueueSubmit(graphicsQueue_, 1, &submit, VK_NULL_HANDLE)) || !ok(vkQueueWaitIdle(graphicsQueue_))) return false;
    vkFreeCommandBuffers(device_, commandPool_, 1, &command);

    updateReflectionDescriptor(reflectionFallbackView_);
    reflectionHasValidContents_ = true;
    return true;
}

void VulkanClearRenderer::updateReflectionDescriptor(VkImageView view) noexcept {
    if (device_ == VK_NULL_HANDLE || reflectionDescriptorSet_ == VK_NULL_HANDLE ||
        reflectionSampler_ == VK_NULL_HANDLE || view == VK_NULL_HANDLE) return;
    VkDescriptorImageInfo imageInfo{};
    imageInfo.sampler = reflectionSampler_;
    imageInfo.imageView = view;
    imageInfo.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    VkWriteDescriptorSet write{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
    write.dstSet = reflectionDescriptorSet_;
    write.dstBinding = 0;
    write.descriptorCount = 1;
    write.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    write.pImageInfo = &imageInfo;
    vkUpdateDescriptorSets(device_, 1, &write, 0, nullptr);
}

void VulkanClearRenderer::destroyReflectionFallbackResources() noexcept {
    if (device_ == VK_NULL_HANDLE) return;
    if (reflectionFallbackView_ != VK_NULL_HANDLE) vkDestroyImageView(device_, reflectionFallbackView_, nullptr);
    if (reflectionFallbackImage_ != VK_NULL_HANDLE) vkDestroyImage(device_, reflectionFallbackImage_, nullptr);
    if (reflectionFallbackMemory_ != VK_NULL_HANDLE) vkFreeMemory(device_, reflectionFallbackMemory_, nullptr);
    reflectionFallbackView_ = VK_NULL_HANDLE;
    reflectionFallbackImage_ = VK_NULL_HANDLE;
    reflectionFallbackMemory_ = VK_NULL_HANDLE;
}

bool VulkanClearRenderer::createReflectionTarget(
    float resolutionScale) noexcept {
    destroyReflectionTarget();

    if (device_ == VK_NULL_HANDLE ||
        swapchainExtent_.width == 0 ||
        swapchainExtent_.height == 0 ||
        !std::isfinite(resolutionScale) ||
        resolutionScale <= 0.0f) {
        return true;
    }

    const float requestedScale =
        std::clamp(
            resolutionScale,
            0.10f,
            1.0f);

    // Match ReflectionTargetPlanner exactly: one uniform cap preserves the
    // source aspect ratio on wide/high-resolution phones instead of clamping
    // each axis independently and stretching the reflected scene.
    constexpr float kMaxReflectionDimension = 1536.0f;
    const float dimensionCapScale =
        std::min(
            kMaxReflectionDimension /
                static_cast<float>(swapchainExtent_.width),
            kMaxReflectionDimension /
                static_cast<float>(swapchainExtent_.height));
    const float scale =
        std::min(
            requestedScale,
            dimensionCapScale);

    const auto scaledDimension =
        [scale](std::uint32_t value) noexcept {
            const auto scaled =
                static_cast<std::uint32_t>(
                    std::max(
                        16.0f,
                        std::floor(
                            static_cast<float>(value) *
                            scale)));
            return std::max(
                16U,
                scaled & ~15U);
        };

    reflectionExtent_.width =
        scaledDimension(swapchainExtent_.width);
    reflectionExtent_.height =
        scaledDimension(swapchainExtent_.height);
    // Keep the requested workload scale as the cache key. The effective
    // allocation scale may be smaller solely because of the hard GPU cap.
    reflectionTargetScale_ = requestedScale;

    const auto createAttachment =
        [&](VkFormat format,
            VkImageUsageFlags usage,
            VkImageAspectFlags aspect,
            VkImage& image,
            VkDeviceMemory& memory,
            VkImageView& view) noexcept {
            VkImageCreateInfo imageInfo{
                VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO
            };
            imageInfo.imageType = VK_IMAGE_TYPE_2D;
            imageInfo.format = format;
            imageInfo.extent = {
                reflectionExtent_.width,
                reflectionExtent_.height,
                1,
            };
            imageInfo.mipLevels = 1;
            imageInfo.arrayLayers = 1;
            imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
            imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
            imageInfo.usage = usage;
            imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
            imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;

            if (!ok(
                    vkCreateImage(
                        device_,
                        &imageInfo,
                        nullptr,
                        &image))) {
                return false;
            }

            VkMemoryRequirements requirements{};
            vkGetImageMemoryRequirements(
                device_,
                image,
                &requirements);

            std::uint32_t memoryType = 0;
            if (!findMemoryType(
                    requirements.memoryTypeBits,
                    VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                    memoryType)) {
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
                        &memory)) ||
                !ok(
                    vkBindImageMemory(
                        device_,
                        image,
                        memory,
                        0))) {
                return false;
            }

            VkImageViewCreateInfo viewInfo{
                VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
            };
            viewInfo.image = image;
            viewInfo.viewType = VK_IMAGE_VIEW_TYPE_2D;
            viewInfo.format = format;
            viewInfo.subresourceRange.aspectMask = aspect;
            viewInfo.subresourceRange.baseMipLevel = 0;
            viewInfo.subresourceRange.levelCount = 1;
            viewInfo.subresourceRange.baseArrayLayer = 0;
            viewInfo.subresourceRange.layerCount = 1;

            return ok(
                vkCreateImageView(
                    device_,
                    &viewInfo,
                    nullptr,
                    &view));
        };

    VkFormatProperties reflectionFormatProperties{};
    vkGetPhysicalDeviceFormatProperties(
        physicalDevice_,
        swapchainFormat_,
        &reflectionFormatProperties);

    const VkFormatFeatureFlags requiredColorFeatures =
        VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT |
        VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT;

    if ((reflectionFormatProperties.optimalTilingFeatures &
         requiredColorFeatures) != requiredColorFeatures) {
        logInfo(
            "Planar reflection format unsupported for sampled color; "
            "falling back");
        destroyReflectionTarget();
        return true;
    }

    const bool colorReady =
        createAttachment(
            swapchainFormat_,
            VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
                VK_IMAGE_USAGE_SAMPLED_BIT,
            VK_IMAGE_ASPECT_COLOR_BIT,
            reflectionColorImage_,
            reflectionColorMemory_,
            reflectionColorView_);

    const bool depthReady =
        colorReady &&
        createAttachment(
            depthFormat_,
            VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT,
            VK_IMAGE_ASPECT_DEPTH_BIT,
            reflectionDepthImage_,
            reflectionDepthMemory_,
            reflectionDepthView_);

    if (!colorReady || !depthReady) {
        logError("Planar reflection target allocation failed; falling back");
        destroyReflectionTarget();
        return true;
    }

    if (!createReflectionPassResources()) {
        logError("Planar reflection pass setup failed; falling back");
        destroyReflectionTarget();
        return true;
    }

    if (reflectionDescriptorSet_ == VK_NULL_HANDLE) {
        logError("Reflection descriptor fallback is unavailable");
        destroyReflectionTarget();
        return true;
    }

    // A newly allocated target starts UNDEFINED. Keep it unavailable until
    // its first capture pass performs the transition to shader-read layout.
    // The persistent descriptor allocation itself survives target churn.
    reflectionHasValidContents_ = false;

    // The capture pass runs before the main pass in the same command buffer,
    // so the live target reaches shader-read layout before it is sampled.
    updateReflectionDescriptor(reflectionColorView_);
    return true;
}

bool VulkanClearRenderer::createReflectionPassResources() noexcept {
    if (reflectionColorView_ == VK_NULL_HANDLE ||
        reflectionDepthView_ == VK_NULL_HANDLE ||
        reflectionExtent_.width == 0 ||
        reflectionExtent_.height == 0) {
        return false;
    }

    VkAttachmentDescription color{};
    color.format = swapchainFormat_;
    color.samples = VK_SAMPLE_COUNT_1_BIT;
    color.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    color.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    color.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    color.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    color.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    color.finalLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;

    VkAttachmentDescription depth{};
    depth.format = depthFormat_;
    depth.samples = VK_SAMPLE_COUNT_1_BIT;
    depth.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    depth.storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depth.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    depth.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depth.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    depth.finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    const std::array<VkAttachmentDescription, 2> attachments{
        color,
        depth,
    };

    VkAttachmentReference colorReference{};
    colorReference.attachment = 0;
    colorReference.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

    VkAttachmentReference depthReference{};
    depthReference.attachment = 1;
    depthReference.layout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    VkSubpassDescription subpass{};
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = 1;
    subpass.pColorAttachments = &colorReference;
    subpass.pDepthStencilAttachment = &depthReference;

    std::array<VkSubpassDependency, 2> dependencies{};

    dependencies[0].srcSubpass = VK_SUBPASS_EXTERNAL;
    dependencies[0].dstSubpass = 0;
    dependencies[0].srcStageMask =
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
    dependencies[0].dstStageMask =
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT |
        VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dependencies[0].srcAccessMask =
        VK_ACCESS_SHADER_READ_BIT;
    dependencies[0].dstAccessMask =
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT |
        VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;

    dependencies[1].srcSubpass = 0;
    dependencies[1].dstSubpass = VK_SUBPASS_EXTERNAL;
    dependencies[1].srcStageMask =
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    dependencies[1].dstStageMask =
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
    dependencies[1].srcAccessMask =
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    dependencies[1].dstAccessMask =
        VK_ACCESS_SHADER_READ_BIT;

    VkRenderPassCreateInfo renderPassInfo{
        VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO
    };
    renderPassInfo.attachmentCount =
        static_cast<std::uint32_t>(attachments.size());
    renderPassInfo.pAttachments = attachments.data();
    renderPassInfo.subpassCount = 1;
    renderPassInfo.pSubpasses = &subpass;
    renderPassInfo.dependencyCount =
        static_cast<std::uint32_t>(dependencies.size());
    renderPassInfo.pDependencies = dependencies.data();

    if (!ok(
            vkCreateRenderPass(
                device_,
                &renderPassInfo,
                nullptr,
                &reflectionRenderPass_))) {
        return false;
    }

    const std::array<VkImageView, 2> views{
        reflectionColorView_,
        reflectionDepthView_,
    };

    VkFramebufferCreateInfo framebufferInfo{
        VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO
    };
    framebufferInfo.renderPass = reflectionRenderPass_;
    framebufferInfo.attachmentCount =
        static_cast<std::uint32_t>(views.size());
    framebufferInfo.pAttachments = views.data();
    framebufferInfo.width = reflectionExtent_.width;
    framebufferInfo.height = reflectionExtent_.height;
    framebufferInfo.layers = 1;

    if (!ok(
            vkCreateFramebuffer(
                device_,
                &framebufferInfo,
                nullptr,
                &reflectionFramebuffer_))) {
        destroyReflectionPassResources();
        return false;
    }

    VkShaderModule vertex = VK_NULL_HANDLE;
    VkShaderModule fragment = VK_NULL_HANDLE;

    if (!createShaderModuleFromAsset(
            "shaders/xziel_first.vert.spv",
            vertex) ||
        !createShaderModuleFromAsset(
            "shaders/xziel_reflection_capture.frag.spv",
            fragment)) {
        if (vertex != VK_NULL_HANDLE) {
            vkDestroyShaderModule(device_, vertex, nullptr);
        }
        if (fragment != VK_NULL_HANDLE) {
            vkDestroyShaderModule(device_, fragment, nullptr);
        }
        destroyReflectionPassResources();
        return false;
    }

    const std::array<VkPipelineShaderStageCreateInfo, 2> stages{{
        {
            VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            nullptr,
            0,
            VK_SHADER_STAGE_VERTEX_BIT,
            vertex,
            "main",
            nullptr,
        },
        {
            VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            nullptr,
            0,
            VK_SHADER_STAGE_FRAGMENT_BIT,
            fragment,
            "main",
            nullptr,
        },
    }};

    VkPipelineVertexInputStateCreateInfo vertexInput{
        VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO
    };
    VkPipelineInputAssemblyStateCreateInfo inputAssembly{
        VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO
    };
    inputAssembly.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;

    VkViewport viewport{};
    viewport.width = static_cast<float>(reflectionExtent_.width);
    viewport.height = static_cast<float>(reflectionExtent_.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;

    VkRect2D scissor{};
    scissor.extent = reflectionExtent_;

    VkPipelineViewportStateCreateInfo viewportState{
        VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO
    };
    viewportState.viewportCount = 1;
    viewportState.pViewports = &viewport;
    viewportState.scissorCount = 1;
    viewportState.pScissors = &scissor;

    VkPipelineRasterizationStateCreateInfo raster{
        VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO
    };
    raster.polygonMode = VK_POLYGON_MODE_FILL;
    raster.cullMode = VK_CULL_MODE_NONE;
    raster.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE;
    raster.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo multisample{
        VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO
    };
    multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

    VkPipelineDepthStencilStateCreateInfo depthStencil{
        VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO
    };
    depthStencil.depthTestEnable = VK_TRUE;
    depthStencil.depthWriteEnable = VK_TRUE;
    depthStencil.depthCompareOp = VK_COMPARE_OP_LESS_OR_EQUAL;

    VkPipelineColorBlendAttachmentState blendAttachment{};
    blendAttachment.colorWriteMask =
        VK_COLOR_COMPONENT_R_BIT |
        VK_COLOR_COMPONENT_G_BIT |
        VK_COLOR_COMPONENT_B_BIT |
        VK_COLOR_COMPONENT_A_BIT;

    VkPipelineColorBlendStateCreateInfo blend{
        VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO
    };
    blend.attachmentCount = 1;
    blend.pAttachments = &blendAttachment;

    VkGraphicsPipelineCreateInfo pipelineInfo{
        VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO
    };
    pipelineInfo.stageCount =
        static_cast<std::uint32_t>(stages.size());
    pipelineInfo.pStages = stages.data();
    pipelineInfo.pVertexInputState = &vertexInput;
    pipelineInfo.pInputAssemblyState = &inputAssembly;
    pipelineInfo.pViewportState = &viewportState;
    pipelineInfo.pRasterizationState = &raster;
    pipelineInfo.pMultisampleState = &multisample;
    pipelineInfo.pDepthStencilState = &depthStencil;
    pipelineInfo.pColorBlendState = &blend;
    pipelineInfo.layout = pipelineLayout_;
    pipelineInfo.renderPass = reflectionRenderPass_;
    pipelineInfo.subpass = 0;

    const VkResult pipelineResult =
        vkCreateGraphicsPipelines(
            device_,
            VK_NULL_HANDLE,
            1,
            &pipelineInfo,
            nullptr,
            &reflectionPipeline_);

    vkDestroyShaderModule(device_, fragment, nullptr);
    vkDestroyShaderModule(device_, vertex, nullptr);

    if (!ok(pipelineResult)) {
        destroyReflectionPassResources();
        return false;
    }

    return true;
}

void VulkanClearRenderer::destroyReflectionPassResources() noexcept {
    if (device_ != VK_NULL_HANDLE) {
        if (reflectionPipeline_ != VK_NULL_HANDLE) {
            vkDestroyPipeline(
                device_,
                reflectionPipeline_,
                nullptr);
        }
        if (reflectionFramebuffer_ != VK_NULL_HANDLE) {
            vkDestroyFramebuffer(
                device_,
                reflectionFramebuffer_,
                nullptr);
        }
        if (reflectionRenderPass_ != VK_NULL_HANDLE) {
            vkDestroyRenderPass(
                device_,
                reflectionRenderPass_,
                nullptr);
        }
    }

    reflectionPipeline_ = VK_NULL_HANDLE;
    reflectionFramebuffer_ = VK_NULL_HANDLE;
    reflectionRenderPass_ = VK_NULL_HANDLE;
}

void VulkanClearRenderer::destroyReflectionTarget() noexcept {
    // Pass/framebuffer resources follow the transient target. Descriptor
    // allocation and sampler lifetime are deliberately independent so the
    // main pipeline can keep one stable descriptor slot across target churn.
    // The descriptor must be considered unusable before its image view is
    // destroyed; a later fallback/live target update is the only path that
    // makes it sampleable again.
    reflectionHasValidContents_ = false;
    if (reflectionFallbackView_ != VK_NULL_HANDLE) {
        updateReflectionDescriptor(reflectionFallbackView_);
        reflectionHasValidContents_ = true;
    }
    destroyReflectionPassResources();

    if (device_ != VK_NULL_HANDLE) {
        if (reflectionDepthView_ != VK_NULL_HANDLE) {
            vkDestroyImageView(
                device_,
                reflectionDepthView_,
                nullptr);
        }
        if (reflectionDepthImage_ != VK_NULL_HANDLE) {
            vkDestroyImage(
                device_,
                reflectionDepthImage_,
                nullptr);
        }
        if (reflectionDepthMemory_ != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                reflectionDepthMemory_,
                nullptr);
        }
        if (reflectionColorView_ != VK_NULL_HANDLE) {
            vkDestroyImageView(
                device_,
                reflectionColorView_,
                nullptr);
        }
        if (reflectionColorImage_ != VK_NULL_HANDLE) {
            vkDestroyImage(
                device_,
                reflectionColorImage_,
                nullptr);
        }
        if (reflectionColorMemory_ != VK_NULL_HANDLE) {
            vkFreeMemory(
                device_,
                reflectionColorMemory_,
                nullptr);
        }
    }

    reflectionColorImage_ = VK_NULL_HANDLE;
    reflectionColorMemory_ = VK_NULL_HANDLE;
    reflectionColorView_ = VK_NULL_HANDLE;
    reflectionDepthImage_ = VK_NULL_HANDLE;
    reflectionDepthMemory_ = VK_NULL_HANDLE;
    reflectionDepthView_ = VK_NULL_HANDLE;
    reflectionExtent_ = {};
    reflectionTargetScale_ = 0.0f;
    reflectionTargetPlaneX_ = 0.0f;
    reflectionTargetPlaneY_ = 1.0f;
    reflectionTargetPlaneZ_ = 0.0f;
    reflectionTargetPlaneD_ = 0.0f;
    reflectionTargetHasPlane_ = false;
    reflectionAllocationBackoffFrames_ = 0;
    reflectionHasValidContents_ = false;
    reflectionInvisibleFrames_ = 0;
}

bool VulkanClearRenderer::createFramebuffers() noexcept {
    if (sceneResolveViews_.size() != depthViews_.size() ||
        sceneResolveViews_.size() != swapchainImages_.size()) {
        return false;
    }

    const bool useMsaa =
        preferredSceneMsaa_ != VK_SAMPLE_COUNT_1_BIT;

    if (useMsaa &&
        sceneColorViews_.size() != sceneResolveViews_.size()) {
        return false;
    }

    framebuffers_.assign(
        sceneResolveViews_.size(),
        VK_NULL_HANDLE);

    for (std::size_t i = 0U; i < framebuffers_.size(); ++i) {
        std::array<VkImageView, 3> attachments{};
        std::uint32_t attachmentCount = 0U;

        if (useMsaa) {
            attachments = {
                sceneColorViews_[i],
                depthViews_[i],
                sceneResolveViews_[i],
            };
            attachmentCount = 3U;
        } else {
            attachments[0] = sceneResolveViews_[i];
            attachments[1] = depthViews_[i];
            attachmentCount = 2U;
        }

        VkFramebufferCreateInfo framebuffer{
            VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO
        };
        framebuffer.renderPass = renderPass_;
        framebuffer.attachmentCount = attachmentCount;
        framebuffer.pAttachments = attachments.data();
        framebuffer.width = sceneExtent_.width;
        framebuffer.height = sceneExtent_.height;
        framebuffer.layers = 1U;

        if (!ok(
                vkCreateFramebuffer(
                    device_,
                    &framebuffer,
                    nullptr,
                    &framebuffers_[i]))) {
            logError("world framebuffer creation failed");
            return false;
        }
    }

    return true;
}

bool VulkanClearRenderer::createUiFramebuffers() noexcept {
    if (uiRenderPass_ == VK_NULL_HANDLE ||
        imageViews_.empty()) {
        return false;
    }

    uiFramebuffers_.assign(
        imageViews_.size(),
        VK_NULL_HANDLE);

    for (std::size_t i = 0U; i < uiFramebuffers_.size(); ++i) {
        const VkImageView attachment = imageViews_[i];

        VkFramebufferCreateInfo framebuffer{
            VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO
        };
        framebuffer.renderPass = uiRenderPass_;
        framebuffer.attachmentCount = 1U;
        framebuffer.pAttachments = &attachment;
        framebuffer.width = swapchainExtent_.width;
        framebuffer.height = swapchainExtent_.height;
        framebuffer.layers = 1U;

        if (!ok(
                vkCreateFramebuffer(
                    device_,
                    &framebuffer,
                    nullptr,
                    &uiFramebuffers_[i]))) {
            logError("native UI framebuffer creation failed");
            return false;
        }
    }

    return true;
}

bool VulkanClearRenderer::createCommandResources() noexcept {
    if (commandPool_ == VK_NULL_HANDLE) {
        VkCommandPoolCreateInfo pool{
            VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO
        };
        pool.flags =
            VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        pool.queueFamilyIndex =
            graphicsQueueFamily_;

        if (!ok(
                vkCreateCommandPool(
                    device_,
                    &pool,
                    nullptr,
                    &commandPool_))) {
            logError("vkCreateCommandPool failed");
            return false;
        }
    }

    commandBuffers_.assign(
        swapchainImages_.size(),
        VK_NULL_HANDLE);

    VkCommandBufferAllocateInfo allocation{
        VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO
    };
    allocation.commandPool =
        commandPool_;
    allocation.level =
        VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    allocation.commandBufferCount =
        static_cast<std::uint32_t>(
            commandBuffers_.size());

    if (!ok(
            vkAllocateCommandBuffers(
                device_,
                &allocation,
                commandBuffers_.data()))) {
        logError("vkAllocateCommandBuffers failed");
        return false;
    }

    return true;
}

bool VulkanClearRenderer::createSyncObjects() noexcept {
    VkSemaphoreCreateInfo semaphore{
        VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO
    };

    VkFenceCreateInfo fence{
        VK_STRUCTURE_TYPE_FENCE_CREATE_INFO
    };
    fence.flags =
        VK_FENCE_CREATE_SIGNALED_BIT;

    for (auto& frame : frames_) {
        if (!ok(
                vkCreateSemaphore(
                    device_,
                    &semaphore,
                    nullptr,
                    &frame.imageAvailable)) ||
            !ok(
                vkCreateSemaphore(
                    device_,
                    &semaphore,
                    nullptr,
                    &frame.renderFinished)) ||
            !ok(
                vkCreateFence(
                    device_,
                    &fence,
                    nullptr,
                    &frame.inFlight))) {
            logError("failed creating sync objects");
            return false;
        }
    }

    return true;
}

bool VulkanClearRenderer::createPerformanceQueries() noexcept {
    destroyPerformanceQueries();

    if (device_ == VK_NULL_HANDLE ||
        timestampValidBits_ == 0U ||
        !std::isfinite(timestampPeriodNs_) ||
        timestampPeriodNs_ <= 0.0f) {
        logInfo("XZIEL_GPU_TIMESTAMPS_UNAVAILABLE");
        return true;
    }

    VkQueryPoolCreateInfo info{
        VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO
    };
    info.queryType =
        VK_QUERY_TYPE_TIMESTAMP;
    info.queryCount =
        kFramesInFlight *
        kGpuTimestampQueriesPerFrame;

    const VkResult result =
        vkCreateQueryPool(
            device_,
            &info,
            nullptr,
            &gpuTimestampQueryPool_);

    if (!ok(result)) {
        gpuTimestampQueryPool_ =
            VK_NULL_HANDLE;
        logInfo("XZIEL_GPU_TIMESTAMPS_UNAVAILABLE");
        return true;
    }

    gpuTimestampValid_.fill(false);
    lastGpuFrameMs_ = 0.0f;
    lastGpuPreWorldMs_ = 0.0f;
    lastGpuWorldMs_ = 0.0f;
    lastGpuCompositeUiMs_ = 0.0f;
    logInfo("XZIEL_GPU_TIMESTAMPS_READY");
    logInfo("XZIEL_GPU_PASS_TIMING_READY passes=3 queries_per_frame=4");
    return true;
}

void VulkanClearRenderer::destroyPerformanceQueries() noexcept {
    if (gpuTimestampQueryPool_ != VK_NULL_HANDLE &&
        device_ != VK_NULL_HANDLE) {
        vkDestroyQueryPool(
            device_,
            gpuTimestampQueryPool_,
            nullptr);
    }

    gpuTimestampQueryPool_ =
        VK_NULL_HANDLE;
    gpuTimestampValid_.fill(false);
    lastGpuFrameMs_ = 0.0f;
    lastGpuPreWorldMs_ = 0.0f;
    lastGpuWorldMs_ = 0.0f;
    lastGpuCompositeUiMs_ = 0.0f;
}

void VulkanClearRenderer::resolvePerformanceQueries(
    std::uint32_t frameSlot) noexcept {
    if (gpuTimestampQueryPool_ == VK_NULL_HANDLE ||
        device_ == VK_NULL_HANDLE ||
        frameSlot >= kFramesInFlight ||
        !gpuTimestampValid_[frameSlot]) {
        return;
    }

    std::array<
        std::uint64_t,
        kGpuTimestampQueriesPerFrame> timestamps{};

    const std::uint32_t queryBase =
        frameSlot *
        kGpuTimestampQueriesPerFrame;

    const VkResult result =
        vkGetQueryPoolResults(
            device_,
            gpuTimestampQueryPool_,
            queryBase,
            kGpuTimestampQueriesPerFrame,
            sizeof(timestamps),
            timestamps.data(),
            sizeof(std::uint64_t),
            VK_QUERY_RESULT_64_BIT);

    gpuTimestampValid_[frameSlot] = false;

    if (!ok(result)) {
        return;
    }

    const auto deltaTicks =
        [&](std::uint64_t begin,
            std::uint64_t end) noexcept
            -> std::uint64_t {
                if (timestampValidBits_ >= 64U) {
                    return end - begin;
                }

                const std::uint64_t mask =
                    (1ULL << timestampValidBits_) -
                    1ULL;

                return
                    (end - begin) &
                    mask;
            };

    const auto toMilliseconds =
        [&](std::uint64_t ticks) noexcept
            -> double {
                return
                    static_cast<double>(ticks) *
                    static_cast<double>(
                        timestampPeriodNs_) *
                    1.0e-6;
            };

    const double frameMs =
        toMilliseconds(
            deltaTicks(
                timestamps[0],
                timestamps[3]));

    const double preWorldMs =
        toMilliseconds(
            deltaTicks(
                timestamps[0],
                timestamps[1]));

    const double worldMs =
        toMilliseconds(
            deltaTicks(
                timestamps[1],
                timestamps[2]));

    const double compositeUiMs =
        toMilliseconds(
            deltaTicks(
                timestamps[2],
                timestamps[3]));

    const auto validDuration =
        [](double value) noexcept {
            return
                std::isfinite(value) &&
                value >= 0.0 &&
                value < 1000.0;
        };

    if (!validDuration(frameMs) ||
        !validDuration(preWorldMs) ||
        !validDuration(worldMs) ||
        !validDuration(compositeUiMs)) {
        return;
    }

    lastGpuFrameMs_ =
        static_cast<float>(frameMs);
    lastGpuPreWorldMs_ =
        static_cast<float>(preWorldMs);
    lastGpuWorldMs_ =
        static_cast<float>(worldMs);
    lastGpuCompositeUiMs_ =
        static_cast<float>(compositeUiMs);

    if (!performanceTimingReadyLogged_) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_PERF_TIMING cpu_render_ms=%.3f gpu_frame_ms=%.3f gpu_preworld_ms=%.3f gpu_world_ms=%.3f gpu_composite_ui_ms=%.3f",
            static_cast<double>(lastCpuRenderMs_),
            static_cast<double>(lastGpuFrameMs_),
            static_cast<double>(lastGpuPreWorldMs_),
            static_cast<double>(lastGpuWorldMs_),
            static_cast<double>(lastGpuCompositeUiMs_));
        performanceTimingReadyLogged_ = true;
    }
}

void VulkanClearRenderer::updateSceneExtent(
    float renderScale) noexcept {
    const float safeScale =
        std::isfinite(renderScale)
        ? std::clamp(renderScale, 0.50f, 1.0f)
        : 1.0f;

    const auto scaledDimension =
        [safeScale](std::uint32_t value) noexcept {
            if (value <= 8U) {
                return std::max(value, 1U);
            }

            std::uint32_t scaled =
                static_cast<std::uint32_t>(
                    std::max(
                        1.0f,
                        std::floor(
                            static_cast<float>(value) *
                            safeScale)));

            scaled = std::min(scaled, value);
            if (scaled >= 16U) {
                scaled &= ~7U;
            }
            return std::max(scaled, 8U);
        };

    sceneExtent_.width =
        scaledDimension(swapchainExtent_.width);
    sceneExtent_.height =
        scaledDimension(swapchainExtent_.height);
    activeRenderScale_ = safeScale;
}

void VulkanClearRenderer::destroySceneTargets() noexcept {
    if (device_ == VK_NULL_HANDLE) {
        framebuffers_.clear();
        sceneColorImages_.clear();
        sceneColorMemory_.clear();
        sceneColorViews_.clear();
        sceneResolveImages_.clear();
        sceneResolveMemory_.clear();
        sceneResolveViews_.clear();
        sceneCompositeDescriptorSets_.clear();
        depthImages_.clear();
        depthMemory_.clear();
        depthViews_.clear();
        return;
    }

    if (sceneCompositeDescriptorPool_ != VK_NULL_HANDLE) {
        vkDestroyDescriptorPool(
            device_,
            sceneCompositeDescriptorPool_,
            nullptr);
        sceneCompositeDescriptorPool_ = VK_NULL_HANDLE;
    }
    sceneCompositeDescriptorSets_.clear();

    for (const auto framebuffer : framebuffers_) {
        if (framebuffer != VK_NULL_HANDLE) {
            vkDestroyFramebuffer(device_, framebuffer, nullptr);
        }
    }
    framebuffers_.clear();

    const auto destroyViews =
        [this](std::vector<VkImageView>& views) noexcept {
            for (const auto view : views) {
                if (view != VK_NULL_HANDLE) {
                    vkDestroyImageView(device_, view, nullptr);
                }
            }
            views.clear();
        };

    const auto destroyImages =
        [this](std::vector<VkImage>& images) noexcept {
            for (const auto image : images) {
                if (image != VK_NULL_HANDLE) {
                    vkDestroyImage(device_, image, nullptr);
                }
            }
            images.clear();
        };

    const auto freeMemory =
        [this](std::vector<VkDeviceMemory>& memory) noexcept {
            for (const auto allocation : memory) {
                if (allocation != VK_NULL_HANDLE) {
                    vkFreeMemory(device_, allocation, nullptr);
                }
            }
            memory.clear();
        };

    destroyViews(sceneColorViews_);
    destroyImages(sceneColorImages_);
    freeMemory(sceneColorMemory_);

    destroyViews(sceneResolveViews_);
    destroyImages(sceneResolveImages_);
    freeMemory(sceneResolveMemory_);

    destroyViews(depthViews_);
    destroyImages(depthImages_);
    freeMemory(depthMemory_);
}

bool VulkanClearRenderer::recreateSceneTargets(
    float renderScale) noexcept {
    const float requested =
        std::isfinite(renderScale)
        ? std::clamp(renderScale, 0.50f, 1.0f)
        : 1.0f;

    const auto createTargets = [this]() noexcept {
        return
            createSceneColorResources() &&
            createSceneResolveResources() &&
            createDepthResources() &&
            createFramebuffers() &&
            createSceneCompositeDescriptors();
    };

    destroySceneTargets();
    updateSceneExtent(requested);

    if (!createTargets()) {
        logError("scaled scene target creation failed; retrying native scale");
        destroySceneTargets();
        updateSceneExtent(1.0f);

        if (!createTargets()) {
            logError("native-scale scene target fallback failed");
            destroySceneTargets();
            return false;
        }
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        kTag,
        "XZIEL_DYNAMIC_RESOLUTION scale=%.2f scene=%ux%u native=%ux%u",
        static_cast<double>(activeRenderScale_),
        sceneExtent_.width,
        sceneExtent_.height,
        swapchainExtent_.width,
        swapchainExtent_.height);

    return true;
}

void VulkanClearRenderer::destroySwapchainResources() noexcept {
    if (device_ == VK_NULL_HANDLE) {
        swapchainImages_.clear();
        imageViews_.clear();
        uiFramebuffers_.clear();
        destroySceneTargets();
        commandBuffers_.clear();
        imageFences_.clear();
        return;
    }

    destroyReflectionTarget();

    if (commandPool_ != VK_NULL_HANDLE &&
        !commandBuffers_.empty()) {
        vkFreeCommandBuffers(
            device_,
            commandPool_,
            static_cast<std::uint32_t>(commandBuffers_.size()),
            commandBuffers_.data());
    }
    commandBuffers_.clear();

    destroySceneTargets();

    for (const auto framebuffer : uiFramebuffers_) {
        if (framebuffer != VK_NULL_HANDLE) {
            vkDestroyFramebuffer(
                device_,
                framebuffer,
                nullptr);
        }
    }
    uiFramebuffers_.clear();

    for (const auto view : imageViews_) {
        if (view != VK_NULL_HANDLE) {
            vkDestroyImageView(
                device_,
                view,
                nullptr);
        }
    }
    imageViews_.clear();

    if (uiBatchPipeline_ != VK_NULL_HANDLE) {
        vkDestroyPipeline(
            device_,
            uiBatchPipeline_,
            nullptr);
        uiBatchPipeline_ = VK_NULL_HANDLE;
    }
    if (uiPipeline_ != VK_NULL_HANDLE) {
        vkDestroyPipeline(device_, uiPipeline_, nullptr);
        uiPipeline_ = VK_NULL_HANDLE;
    }
    if (uiPipelineLayout_ != VK_NULL_HANDLE) {
        vkDestroyPipelineLayout(device_, uiPipelineLayout_, nullptr);
        uiPipelineLayout_ = VK_NULL_HANDLE;
    }

    if (sceneCompositePipeline_ != VK_NULL_HANDLE) {
        vkDestroyPipeline(device_, sceneCompositePipeline_, nullptr);
        sceneCompositePipeline_ = VK_NULL_HANDLE;
    }
    if (sceneCompositePipelineLayout_ != VK_NULL_HANDLE) {
        vkDestroyPipelineLayout(
            device_,
            sceneCompositePipelineLayout_,
            nullptr);
        sceneCompositePipelineLayout_ = VK_NULL_HANDLE;
    }
    if (sceneCompositeSampler_ != VK_NULL_HANDLE) {
        vkDestroySampler(
            device_,
            sceneCompositeSampler_,
            nullptr);
        sceneCompositeSampler_ = VK_NULL_HANDLE;
    }
    if (sceneCompositeDescriptorSetLayout_ != VK_NULL_HANDLE) {
        vkDestroyDescriptorSetLayout(
            device_,
            sceneCompositeDescriptorSetLayout_,
            nullptr);
        sceneCompositeDescriptorSetLayout_ = VK_NULL_HANDLE;
    }

    if (graphicsPipeline_ != VK_NULL_HANDLE) {
        vkDestroyPipeline(device_, graphicsPipeline_, nullptr);
        graphicsPipeline_ = VK_NULL_HANDLE;
    }
    if (pipelineLayout_ != VK_NULL_HANDLE) {
        vkDestroyPipelineLayout(device_, pipelineLayout_, nullptr);
        pipelineLayout_ = VK_NULL_HANDLE;
    }

    destroyReflectionFallbackResources();

    if (reflectionDescriptorPool_ != VK_NULL_HANDLE) {
        vkDestroyDescriptorPool(
            device_,
            reflectionDescriptorPool_,
            nullptr);
        reflectionDescriptorPool_ = VK_NULL_HANDLE;
        reflectionDescriptorSet_ = VK_NULL_HANDLE;
    }
    if (reflectionSampler_ != VK_NULL_HANDLE) {
        vkDestroySampler(device_, reflectionSampler_, nullptr);
        reflectionSampler_ = VK_NULL_HANDLE;
    }
    if (reflectionDescriptorSetLayout_ != VK_NULL_HANDLE) {
        vkDestroyDescriptorSetLayout(
            device_,
            reflectionDescriptorSetLayout_,
            nullptr);
        reflectionDescriptorSetLayout_ = VK_NULL_HANDLE;
    }

    if (uiRenderPass_ != VK_NULL_HANDLE) {
        vkDestroyRenderPass(device_, uiRenderPass_, nullptr);
        uiRenderPass_ = VK_NULL_HANDLE;
    }
    if (renderPass_ != VK_NULL_HANDLE) {
        vkDestroyRenderPass(device_, renderPass_, nullptr);
        renderPass_ = VK_NULL_HANDLE;
    }

    if (swapchain_ != VK_NULL_HANDLE) {
        if (swappyInitialized_) {
            SwappyVk_destroySwapchain(device_, swapchain_);
            swappyInitialized_ = false;
            refreshDurationNs_ = 0;
        }

        vkDestroySwapchainKHR(
            device_,
            swapchain_,
            nullptr);
        swapchain_ = VK_NULL_HANDLE;
    }

    swapchainImages_.clear();
    imageFences_.clear();
}

bool VulkanClearRenderer::recreateSwapchain() noexcept {
    if (device_ == VK_NULL_HANDLE ||
        window_ == nullptr) {
        return false;
    }

    if (ANativeWindow_getWidth(window_) <= 0 ||
        ANativeWindow_getHeight(window_) <= 0) {
        return true;
    }

    const VkResult idleResult =
        vkDeviceWaitIdle(device_);

    if (!ok(idleResult)) {
        if (idleResult == VK_ERROR_DEVICE_LOST) {
            deviceLost_ = true;
        }
        return false;
    }

    weaponMesh_.shutdown();
    sanctumMesh_.shutdown();

    destroySwapchainResources();

    const bool success =
        createSwapchain() &&
        createRenderPass() &&
        createUiRenderPass() &&
        createGraphicsPipeline() &&
        createSceneCompositePipeline() &&
        createUiPipeline() &&
        createImageViews() &&
        createSceneColorResources() &&
        createSceneResolveResources() &&
        createDepthResources() &&
        createCommandResources() &&
        createReflectionFallbackResources() &&
        createFramebuffers() &&
        createUiFramebuffers() &&
        createSceneCompositeDescriptors();

    if (!success) {
        logError("Swapchain recreation failed");
        return false;
    }

    (void) sanctumMesh_.initialize(
        physicalDevice_,
        device_,
        graphicsQueue_,
        graphicsQueueFamily_,
        commandPool_,
        renderPass_,
        preferredSceneMsaa_,
        assetManager_,
        "models/xziel/sanctum/sanctum.xzsm");

    (void) weaponMesh_.initialize(
        physicalDevice_,
        device_,
        graphicsQueue_,
        graphicsQueueFamily_,
        commandPool_,
        renderPass_,
        preferredSceneMsaa_,
        assetManager_,
        "models/xziel/weapons/standard_rifle.xzsm");

    return true;
}

bool VulkanClearRenderer::recordDrawCommand(
    std::uint32_t imageIndex,
    std::uint32_t frameSlot,
    float timeSeconds,
    const VulkanCamera& camera,
    const VulkanHudState& hud,
    const VulkanSceneState& scene,
    const VulkanEnvironmentState& environment) noexcept {
    if (imageIndex >= commandBuffers_.size() ||
        imageIndex >= framebuffers_.size()) {
        return false;
    }

    const VkCommandBuffer command =
        commandBuffers_[imageIndex];

    if (!ok(
            vkResetCommandBuffer(
                command,
                0))) {
        logError("vkResetCommandBuffer failed");
        return false;
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
        logError("vkBeginCommandBuffer failed");
        return false;
    }

    if (gpuTimestampQueryPool_ != VK_NULL_HANDLE &&
        frameSlot < kFramesInFlight) {
        const std::uint32_t queryBase =
            frameSlot *
            kGpuTimestampQueriesPerFrame;

        gpuTimestampValid_[frameSlot] = false;

        vkCmdResetQueryPool(
            command,
            gpuTimestampQueryPool_,
            queryBase,
            kGpuTimestampQueriesPerFrame);

        vkCmdWriteTimestamp(
            command,
            VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
            gpuTimestampQueryPool_,
            queryBase);
    }

    const float pulse =
        0.5f +
        0.5f * std::sin(
            timeSeconds * 1.45f);

    std::array<VkClearValue, 2> clears{};

    const float lightning =
        std::clamp(
            environment.lightningFlash,
            0.0f,
            1.0f);

    clears[0].color.float32[0] =
        0.004f +
        pulse * 0.002f +
        lightning * 0.14f;

    clears[0].color.float32[1] =
        0.009f +
        pulse * 0.003f +
        lightning * 0.18f;

    clears[0].color.float32[2] =
        0.016f +
        pulse * 0.005f +
        lightning * 0.24f;
    clears[0].color.float32[3] =
        1.0f;

    clears[1].depthStencil.depth =
        1.0f;
    clears[1].depthStencil.stencil =
        0;

    VkRenderPassBeginInfo render{
        VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO
    };
    render.renderPass =
        renderPass_;
    render.framebuffer =
        framebuffers_[imageIndex];
    render.renderArea.offset =
        {0, 0};
    render.renderArea.extent =
        sceneExtent_;
    render.clearValueCount =
        static_cast<std::uint32_t>(
            clears.size());
    render.pClearValues =
        clears.data();

    const float reflectionCoverage =
        std::clamp(
            environment.planarReflectionScreenCoverage,
            0.0f,
            1.0f);

    // Refresh the offscreen planar scene before the main pass. The first
    // implementation intentionally renders a compact subset of the room with
    // a reflected camera; the target is already transitioned to shader-read
    // layout by the reflection render pass for the material sampling stage.
    // Tiny reflective surfaces can retain the previous target longer. This
    // is deliberately quantized to avoid unstable frame-to-frame scheduling.
    const std::uint32_t coverageIntervalMultiplier =
        reflectionCoverage < 0.025f
        ? 4U
        : (reflectionCoverage < 0.08f ? 2U : 1U);
    const std::uint32_t reflectionUpdateInterval =
        std::clamp(
            environment.planarReflectionUpdateEveryNFrames *
                coverageIntervalMultiplier,
            1U,
            8U);
    const bool reflectionDue =
        !reflectionHasValidContents_ ||
        reflectionFrameCounter_ % reflectionUpdateInterval == 0;

    if (reflectionRenderPass_ != VK_NULL_HANDLE &&
        reflectionFramebuffer_ != VK_NULL_HANDLE &&
        reflectionPipeline_ != VK_NULL_HANDLE &&
        environment.maxPlanarReflectionPasses > 0 &&
        environment.planarReflectionVisible &&
        reflectionCoverage > 0.0025f &&
        reflectionDue) {
        std::array<VkClearValue, 2> reflectionClears{};
        reflectionClears[0].color.float32[0] =
            clears[0].color.float32[0] * 0.55f;
        reflectionClears[0].color.float32[1] =
            clears[0].color.float32[1] * 0.65f;
        reflectionClears[0].color.float32[2] =
            clears[0].color.float32[2] * 0.80f;
        reflectionClears[0].color.float32[3] = 1.0f;
        reflectionClears[1].depthStencil.depth = 1.0f;

        VkRenderPassBeginInfo reflectionBegin{
            VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO
        };
        reflectionBegin.renderPass = reflectionRenderPass_;
        reflectionBegin.framebuffer = reflectionFramebuffer_;
        reflectionBegin.renderArea.extent = reflectionExtent_;
        reflectionBegin.clearValueCount =
            static_cast<std::uint32_t>(reflectionClears.size());
        reflectionBegin.pClearValues = reflectionClears.data();

        vkCmdBeginRenderPass(
            command,
            &reflectionBegin,
            VK_SUBPASS_CONTENTS_INLINE);
        vkCmdBindPipeline(
            command,
            VK_PIPELINE_BIND_POINT_GRAPHICS,
            reflectionPipeline_);

        const float reflectedAspect =
            reflectionExtent_.height > 0
            ? static_cast<float>(reflectionExtent_.width) /
              static_cast<float>(reflectionExtent_.height)
            : 1.0f;
        constexpr float kProjectionDegreesToRadians =
            0.01745329251994329577f;
        const float reflectedFovDegrees =
            std::clamp(
                std::isfinite(camera.verticalFovDegrees)
                    ? camera.verticalFovDegrees
                    : 72.0f,
                50.0f,
                110.0f);
        const float reflectedFocal =
            1.0f /
            std::tan(
                reflectedFovDegrees *
                0.5f *
                kProjectionDegreesToRadians);
        const float reflectedFocalOverAspect =
            reflectedFocal /
            std::max(
                reflectedAspect,
                0.25f);

        // REFLECTION_CAMERA_PRECOMPUTE_V1
        // Plane orientation and reflected camera are invariant across every
        // object draw in this capture pass. Resolve them once per pass.
        float reflectedPlaneNx =
            environment.planarPlaneNormalX;
        float reflectedPlaneNy =
            environment.planarPlaneNormalY;
        float reflectedPlaneNz =
            environment.planarPlaneNormalZ;
        float reflectedPlaneD =
            environment.planarPlaneDistance;
        const float reflectedPlaneLength =
            std::sqrt(
                reflectedPlaneNx * reflectedPlaneNx +
                reflectedPlaneNy * reflectedPlaneNy +
                reflectedPlaneNz * reflectedPlaneNz);
        if (!std::isfinite(reflectedPlaneLength) ||
            reflectedPlaneLength < 0.0001f) {
            reflectedPlaneNx = 0.0f;
            reflectedPlaneNy = 1.0f;
            reflectedPlaneNz = 0.0f;
            reflectedPlaneD = 1.48f;
        } else {
            const float inversePlaneLength =
                1.0f /
                reflectedPlaneLength;
            reflectedPlaneNx *= inversePlaneLength;
            reflectedPlaneNy *= inversePlaneLength;
            reflectedPlaneNz *= inversePlaneLength;
            reflectedPlaneD =
                std::isfinite(reflectedPlaneD)
                ? reflectedPlaneD *
                    inversePlaneLength
                : 0.0f;
        }

        float reflectedCameraDistance =
            reflectedPlaneNx * camera.x +
            reflectedPlaneNy * camera.y +
            reflectedPlaneNz * camera.z +
            reflectedPlaneD;
        if (reflectedCameraDistance < 0.0f) {
            reflectedPlaneNx = -reflectedPlaneNx;
            reflectedPlaneNy = -reflectedPlaneNy;
            reflectedPlaneNz = -reflectedPlaneNz;
            reflectedPlaneD = -reflectedPlaneD;
            reflectedCameraDistance =
                -reflectedCameraDistance;
        }

        const float reflectedCameraX =
            camera.x -
            2.0f *
                reflectedCameraDistance *
                reflectedPlaneNx;
        const float reflectedCameraY =
            camera.y -
            2.0f *
                reflectedCameraDistance *
                reflectedPlaneNy;
        const float reflectedCameraZ =
            camera.z -
            2.0f *
                reflectedCameraDistance *
                reflectedPlaneNz;

        const float safeYaw =
            std::isfinite(camera.yawRadians)
            ? camera.yawRadians
            : 0.0f;
        const float safePitch =
            std::isfinite(camera.pitchRadians)
            ? camera.pitchRadians
            : 0.0f;
        const float cosPitch =
            std::cos(safePitch);
        float reflectedForwardX =
            std::sin(safeYaw) *
            cosPitch;
        float reflectedForwardY =
            -std::sin(safePitch);
        float reflectedForwardZ =
            std::cos(safeYaw) *
            cosPitch;
        const float reflectedForwardDotPlane =
            reflectedForwardX * reflectedPlaneNx +
            reflectedForwardY * reflectedPlaneNy +
            reflectedForwardZ * reflectedPlaneNz;
        reflectedForwardX -=
            2.0f *
            reflectedForwardDotPlane *
            reflectedPlaneNx;
        reflectedForwardY -=
            2.0f *
            reflectedForwardDotPlane *
            reflectedPlaneNy;
        reflectedForwardZ -=
            2.0f *
            reflectedForwardDotPlane *
            reflectedPlaneNz;
        const float reflectedHorizontalForward =
            std::sqrt(
                reflectedForwardX *
                    reflectedForwardX +
                reflectedForwardZ *
                    reflectedForwardZ);
        const float reflectedCameraYaw =
            std::atan2(
                reflectedForwardX,
                reflectedForwardZ);
        const float reflectedCameraPitch =
            std::atan2(
                -reflectedForwardY,
                reflectedHorizontalForward);
        const float reflectedCameraCosYaw =
            std::cos(reflectedCameraYaw);
        const float reflectedCameraSinYaw =
            std::sin(reflectedCameraYaw);
        const float reflectedCameraCosPitch =
            std::cos(reflectedCameraPitch);
        const float reflectedCameraSinPitch =
            std::sin(reflectedCameraPitch);

        // REFLECTION_PUSH_BASE_CACHE_V1
        // Everything below except object transform/material is invariant for
        // all draws in this capture pass. Build once and copy per object.
        PushConstants reflectedBasePush{};
        reflectedBasePush.timeSeconds =
            std::isfinite(timeSeconds)
            ? timeSeconds
            : 0.0f;
        reflectedBasePush.aspect =
            reflectedFocalOverAspect;
        reflectedBasePush.horrorPulse =
            pulse;
        reflectedBasePush.cameraX =
            reflectedCameraX;
        reflectedBasePush.cameraY =
            reflectedCameraY;
        reflectedBasePush.cameraZ =
            reflectedCameraZ;
        reflectedBasePush.cameraYawRadians =
            reflectedCameraYaw;
        reflectedBasePush.cameraPitchRadians =
            reflectedCameraPitch;
        reflectedBasePush.verticalFovDegrees =
            reflectedFovDegrees;
        reflectedBasePush.fogDensity =
            std::clamp(
                environment.fogDensity,
                0.0f,
                1.0f);
        reflectedBasePush.lightningFlash =
            std::clamp(
                environment.lightningFlash,
                0.0f,
                2.0f);
        reflectedBasePush.wetness =
            std::clamp(
                environment.wetness,
                0.0f,
                1.0f);
        reflectedBasePush.rainIntensity =
            std::clamp(
                environment.rainIntensity,
                0.0f,
                1.0f);
        reflectedBasePush.waterWavePhase =
            environment.waterWavePhase;
        reflectedBasePush.waterFoamStrength =
            std::clamp(
                environment.waterFoamStrength,
                0.0f,
                1.0f);
        reflectedBasePush.waterReflectionStrength =
            0.0f;
        reflectedBasePush.waterRefractionStrength =
            0.0f;
        reflectedBasePush.waterRoughness =
            std::clamp(
                environment.waterRoughness,
                0.02f,
                0.85f);
        reflectedBasePush.waterQualityScale =
            std::clamp(
                environment.postProcessScale,
                0.35f,
                1.0f);
        reflectedBasePush.waterParticleScale =
            std::clamp(
                environment.particleDensityScale,
                0.25f,
                1.0f);
        reflectedBasePush.waterFogScale =
            reflectedFocal;
        reflectedBasePush.reflectionPlaneX =
            reflectedPlaneNx;
        reflectedBasePush.reflectionPlaneY =
            reflectedPlaneNy;
        reflectedBasePush.reflectionPlaneZ =
            reflectedPlaneNz;
        reflectedBasePush.reflectionPlaneDistance =
            reflectedPlaneD;

        const auto drawReflectedBox = [&](
            float tx,
            float ty,
            float tz,
            float sx,
            float sy,
            float sz,
            float materialId) noexcept {
            PushConstants push =
                reflectedBasePush;
            push.materialId =
                materialId;
            push.translationX = tx;
            push.translationY = ty;
            push.translationZ = tz;
            push.scaleX = sx;
            push.scaleY = sy;
            push.scaleZ = sz;

            const bool reflectiveMaterial =
                materialId == 13.0f ||
                materialId == 14.0f;
            if (!reflectiveMaterial) {
                push.reflectionPlaneX =
                    reflectedCameraCosYaw;
                push.reflectionPlaneY =
                    reflectedCameraSinYaw;
                push.reflectionPlaneZ =
                    reflectedCameraCosPitch;
                push.reflectionPlaneDistance =
                    reflectedCameraSinPitch;
            }

            vkCmdPushConstants(
                command,
                pipelineLayout_,
                VK_SHADER_STAGE_VERTEX_BIT |
                    VK_SHADER_STAGE_FRAGMENT_BIT,
                0,
                static_cast<std::uint32_t>(sizeof(PushConstants)),
                &push);
            vkCmdDraw(command, 36, 1, 0, 0);
        };

        // Render authored map geometry into the planar capture. Reflective
        // surfaces themselves are omitted to avoid recursive feedback.
        const std::size_t reflectedMapBoxCount =
            std::min(
                scene.mapBoxCount,
                scene.mapBoxes.size());

        for (std::size_t i = 0;
             i < reflectedMapBoxCount;
             ++i) {
            const auto& box = scene.mapBoxes[i];

            if (!box.visible ||
                box.materialId == 13.0f ||
                box.materialId == 14.0f) {
                continue;
            }

            drawReflectedBox(
                box.x,
                box.y,
                box.z,
                box.scaleX,
                box.scaleY,
                box.scaleZ,
                box.materialId);
        }

        const std::size_t reflectedZombieCount =
            std::min(scene.zombieCount, scene.zombies.size());
        for (std::size_t i = 0; i < reflectedZombieCount; ++i) {
            const auto& zombie = scene.zombies[i];
            if (!zombie.visible) {
                continue;
            }
            drawReflectedBox(
                zombie.x,
                zombie.y + 1.08f,
                zombie.z,
                0.34f,
                0.55f,
                0.22f,
                4.0f);
            drawReflectedBox(
                zombie.x,
                zombie.y + 1.73f,
                zombie.z + 0.01f,
                0.23f,
                0.24f,
                0.22f,
                5.0f);
        }

        vkCmdEndRenderPass(command);
        reflectionHasValidContents_ = true;
    }

    ++reflectionFrameCounter_;

    if (gpuTimestampQueryPool_ != VK_NULL_HANDLE &&
        frameSlot < kFramesInFlight) {
        const std::uint32_t queryBase =
            frameSlot *
            kGpuTimestampQueriesPerFrame;

        vkCmdWriteTimestamp(
            command,
            VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
            gpuTimestampQueryPool_,
            queryBase + 1U);
    }

    vkCmdBeginRenderPass(
        command,
        &render,
        VK_SUBPASS_CONTENTS_INLINE);

    VkViewport worldViewport{};
    worldViewport.width =
        static_cast<float>(sceneExtent_.width);
    worldViewport.height =
        static_cast<float>(sceneExtent_.height);
    worldViewport.minDepth = 0.0f;
    worldViewport.maxDepth = 1.0f;

    VkRect2D worldScissor{};
    worldScissor.extent = sceneExtent_;

    vkCmdSetViewport(
        command,
        0U,
        1U,
        &worldViewport);
    vkCmdSetScissor(
        command,
        0U,
        1U,
        &worldScissor);

    if (graphicsPipeline_ == VK_NULL_HANDLE ||
        pipelineLayout_ == VK_NULL_HANDLE) {
        vkCmdEndRenderPass(command);
        logError("graphics pipeline missing");
        return false;
    }

    if (sanctumMesh_.ready()) {
        const std::size_t streamDoorCount =
            std::min(
                scene.doorCount,
                scene.doors.size());

        for (std::size_t doorIndex = 0U;
             doorIndex < streamDoorCount;
             ++doorIndex) {
            const auto& door =
                scene.doors[doorIndex];

            if (door.id == 0U) {
                continue;
            }

            sanctumMesh_.setStreamingPortalOpen(
                door.id,
                door.openProgress >= 0.95f);
        }

        const float sanctumAspect =
            sceneExtent_.height > 0U
            ? static_cast<float>(
                  sceneExtent_.width) /
              static_cast<float>(
                  sceneExtent_.height)
            : 1.0f;

        StaticMeshCameraState sanctumCamera{};
        sanctumCamera.x = camera.x;
        sanctumCamera.y = camera.y;
        sanctumCamera.z = camera.z;
        sanctumCamera.yawRadians =
            camera.yawRadians;
        sanctumCamera.pitchRadians =
            camera.pitchRadians;
        sanctumCamera.verticalFovDegrees =
            camera.verticalFovDegrees;
        sanctumCamera.aspect =
            sanctumAspect;

        StaticMeshEnvironmentState sanctumEnvironment{};
        sanctumEnvironment.fogDensity =
            environment.fogDensity;
        sanctumEnvironment.lightningFlash =
            environment.lightningFlash;
        sanctumEnvironment.memoryPressure =
            environment.memoryPressure;

        sanctumMesh_.record(
            command,
            sceneExtent_,
            frameSlot,
            sanctumCamera,
            sanctumEnvironment);

        // CI_SOFTWARE_VULKAN_FRESH_SCENE_COST_V1
        // SwiftShader can run the HQ scene near 1 FPS, so a 120-frame
        // telemetry period leaves the Android touch tour validating an old
        // camera sample. Real GPUs retain the low-noise 120-frame cadence;
        // CPU/software Vulkan emits the current post-cull scene cost every
        // frame so CI validates the camera that was actually captured.
        const std::uint32_t sceneCostTelemetryPeriod =
            physicalDeviceType_ == VK_PHYSICAL_DEVICE_TYPE_CPU
            ? 1U
            : 120U;

        if (performanceTelemetryFrame_ %
                sceneCostTelemetryPeriod == 0U) {
            const auto meshStats =
                sanctumMesh_.frameStats();

            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_SCENE_COST visible_batches=%u culled_batches=%u draws=%u triangles=%llu",
                meshStats.visibleBatches,
                meshStats.culledBatches,
                meshStats.drawCalls,
                static_cast<unsigned long long>(
                    meshStats.submittedTriangles));
        }
    }

    // The current AKM source imports correctly as textured geometry, but its
    // baked rig transforms are not yet trustworthy in the static XZSM
    // viewmodel path. Keep it packaged/tested, but do not draw a malformed
    // streak across the player's screen. The procedural blockout also stays
    // suppressed because a clean no-viewmodel checkpoint is preferable to
    // regressing to the toy-looking placeholder.
    constexpr bool kImportedWeaponViewmodelEnabled = true;

    if (kImportedWeaponViewmodelEnabled &&
        weaponMesh_.ready()) {
        const float viewAspect =
            sceneExtent_.height > 0U
            ? static_cast<float>(
                  sceneExtent_.width) /
              static_cast<float>(
                  sceneExtent_.height)
            : 1.0f;

        const float adsRaw =
            std::clamp(
                hud.weaponAdsAlpha,
                0.0f,
                1.0f);

        // Preserve controller timing but ease the visual pose like a real FPS
        // viewmodel instead of linearly sliding the gun toward the sight.
        const float ads =
            adsRaw *
            adsRaw *
            (3.0f - 2.0f * adsRaw);

        const float reload =
            std::clamp(
                hud.weaponReloadAlpha,
                0.0f,
                1.0f);

        const float reloadArc =
            std::sin(
                reload *
                3.14159265358979323846f);

        const float fire =
            std::clamp(
                hud.weaponFireAlpha,
                0.0f,
                1.0f);

        const float lowering =
            std::clamp(
                hud.viewmodelLowering,
                0.0f,
                1.0f);

        StaticMeshViewmodelState weaponState{};
        const auto& viewmodel =
            hud.weaponViewmodel;
        const auto& hip =
            viewmodel.hip;
        const auto& aimed =
            viewmodel.ads;

        // Assets enter the renderer in canonical XZIEL first-person space.
        // Every weapon owns its own calibrated hip/ADS poses so changing gun
        // models no longer requires editing renderer constants.
        weaponState.x =
            hip.x * (1.0f - ads) +
            aimed.x * ads +
            viewmodel.loweringX * lowering;
        weaponState.y =
            hip.y * (1.0f - ads) +
            aimed.y * ads +
            viewmodel.reloadY * reloadArc +
            viewmodel.loweringY * lowering +
            viewmodel.fireY * fire;
        weaponState.z =
            hip.z * (1.0f - ads) +
            aimed.z * ads +
            viewmodel.reloadZ * reloadArc +
            viewmodel.fireZ * fire +
            viewmodel.loweringZ * lowering;
        weaponState.scale =
            hip.scale * (1.0f - ads) +
            aimed.scale * ads;
        weaponState.yawRadians =
            hip.yawRadians * (1.0f - ads) +
            aimed.yawRadians * ads +
            viewmodel.reloadYawRadians * reloadArc;
        weaponState.pitchRadians =
            hip.pitchRadians * (1.0f - ads) +
            aimed.pitchRadians * ads +
            viewmodel.reloadPitchRadians * reloadArc +
            viewmodel.firePitchRadians * fire;
        weaponState.rollRadians =
            hip.rollRadians * (1.0f - ads) +
            aimed.rollRadians * ads +
            viewmodel.reloadRollRadians * reloadArc +
            viewmodel.fireRollRadians * fire;
        weaponState.verticalFovDegrees =
            std::clamp(
                viewmodel.verticalFovDegrees,
                55.0f,
                90.0f);
        weaponState.aspect =
            viewAspect;

        weaponMesh_.recordViewmodel(
            command,
            sceneExtent_,
            frameSlot,
            weaponState);
    }

    vkCmdBindPipeline(
        command,
        VK_PIPELINE_BIND_POINT_GRAPHICS,
        graphicsPipeline_);

    // xziel_first.frag statically declares the reflection sampler. Vulkan
    // therefore requires descriptor set 0 to be valid for every main-pipeline
    // draw, even when the current material is not water. Never submit a draw
    // with an unbound or stale descriptor after a quality downgrade, target
    // reallocation, or allocation failure.
    if (reflectionDescriptorSet_ == VK_NULL_HANDLE) {
        vkCmdEndRenderPass(command);
        logError("reflection descriptor unavailable; refusing invalid Vulkan draw");
        return false;
    }

    vkCmdBindDescriptorSets(
        command,
        VK_PIPELINE_BIND_POINT_GRAPHICS,
        pipelineLayout_,
        0,
        1,
        &reflectionDescriptorSet_,
        0,
        nullptr);

    const float safeTime =
        std::isfinite(timeSeconds)
        ? timeSeconds
        : 0.0f;

    const float aspect =
        sceneExtent_.height > 0
        ? static_cast<float>(
              sceneExtent_.width) /
          static_cast<float>(
              sceneExtent_.height)
        : 1.0f;
    constexpr float kProjectionDegreesToRadians =
        0.01745329251994329577f;
    const float projectionFovDegrees =
        std::clamp(
            std::isfinite(camera.verticalFovDegrees)
                ? camera.verticalFovDegrees
                : 72.0f,
            50.0f,
            110.0f);
    const float projectionFocal =
        1.0f /
        std::tan(
            projectionFovDegrees *
            0.5f *
            kProjectionDegreesToRadians);
    const float projectionFocalOverAspect =
        projectionFocal /
        std::max(
            aspect,
            0.25f);

    const float safeCameraX =
        std::isfinite(camera.x)
        ? camera.x
        : 0.0f;
    const float safeCameraY =
        std::isfinite(camera.y)
        ? camera.y
        : 0.14f;
    const float safeCameraZ =
        std::isfinite(camera.z)
        ? camera.z
        : -2.55f;
    const float safeCameraYaw =
        std::isfinite(camera.yawRadians)
        ? camera.yawRadians
        : 0.0f;
    const float safeCameraPitch =
        std::isfinite(camera.pitchRadians)
        ? camera.pitchRadians
        : 0.0f;

    // CAMERA_TRIG_CPU_CACHE_V1
    // Camera orientation is pass-invariant. Compute the four trig terms once
    // on CPU and place them in reflectionPlane for non-reflective draws, where
    // those push-constant slots are otherwise unused.
    const float mainCameraCosYaw =
        std::cos(safeCameraYaw);
    const float mainCameraSinYaw =
        std::sin(safeCameraYaw);
    const float mainCameraCosPitch =
        std::cos(safeCameraPitch);
    const float mainCameraSinPitch =
        std::sin(safeCameraPitch);

    float mainPlaneNx =
        environment.planarPlaneNormalX;
    float mainPlaneNy =
        environment.planarPlaneNormalY;
    float mainPlaneNz =
        environment.planarPlaneNormalZ;
    float mainPlaneD =
        environment.planarPlaneDistance;
    const float mainPlaneLength =
        std::sqrt(
            mainPlaneNx * mainPlaneNx +
            mainPlaneNy * mainPlaneNy +
            mainPlaneNz * mainPlaneNz);
    if (!std::isfinite(mainPlaneLength) ||
        mainPlaneLength < 0.0001f) {
        mainPlaneNx = 0.0f;
        mainPlaneNy = 1.0f;
        mainPlaneNz = 0.0f;
        mainPlaneD = 1.48f;
    } else {
        const float inverseMainPlaneLength =
            1.0f /
            mainPlaneLength;
        mainPlaneNx *= inverseMainPlaneLength;
        mainPlaneNy *= inverseMainPlaneLength;
        mainPlaneNz *= inverseMainPlaneLength;
        mainPlaneD =
            std::isfinite(mainPlaneD)
            ? mainPlaneD *
                inverseMainPlaneLength
            : 0.0f;
    }
    const float mainCameraSide =
        mainPlaneNx * safeCameraX +
        mainPlaneNy * safeCameraY +
        mainPlaneNz * safeCameraZ +
        mainPlaneD;
    if (mainCameraSide < 0.0f) {
        mainPlaneNx = -mainPlaneNx;
        mainPlaneNy = -mainPlaneNy;
        mainPlaneNz = -mainPlaneNz;
        mainPlaneD = -mainPlaneD;
    }

    // MAIN_PUSH_BASE_CACHE_V1
    // Camera/environment/reflection state is invariant for all primitive draws
    // in this pass. Build it once and patch only object-local fields.
    PushConstants mainBasePush{};
    mainBasePush.timeSeconds =
        safeTime;
    mainBasePush.aspect =
        projectionFocalOverAspect;
    mainBasePush.horrorPulse =
        pulse;
    mainBasePush.cameraX =
        safeCameraX;
    mainBasePush.cameraY =
        safeCameraY;
    mainBasePush.cameraZ =
        safeCameraZ;
    mainBasePush.cameraYawRadians =
        safeCameraYaw;
    mainBasePush.cameraPitchRadians =
        safeCameraPitch;
    mainBasePush.verticalFovDegrees =
        projectionFovDegrees;
    mainBasePush.cameraPadding0 =
        static_cast<float>(
            environment.planarReflectionMaterialId);
    mainBasePush.fogDensity =
        std::clamp(
            environment.fogDensity,
            0.0f,
            1.0f);
    mainBasePush.lightningFlash =
        std::clamp(
            environment.lightningFlash,
            0.0f,
            2.0f);
    mainBasePush.wetness =
        std::clamp(
            environment.wetness,
            0.0f,
            1.0f);
    mainBasePush.rainIntensity =
        std::clamp(
            environment.rainIntensity,
            0.0f,
            1.0f);
    mainBasePush.waterWavePhase =
        environment.waterWavePhase;
    mainBasePush.waterFoamStrength =
        std::clamp(
            environment.waterFoamStrength,
            0.0f,
            1.0f);
    mainBasePush.waterReflectionStrength =
        std::clamp(
            environment.waterReflectionStrength,
            0.0f,
            1.0f);
    mainBasePush.waterRefractionStrength =
        std::clamp(
            environment.waterRefractionStrength,
            0.0f,
            1.0f);
    mainBasePush.waterRoughness =
        std::clamp(
            environment.waterRoughness,
            0.02f,
            0.85f);
    mainBasePush.waterQualityScale =
        std::clamp(
            environment.postProcessScale,
            0.35f,
            1.0f);
    mainBasePush.waterParticleScale =
        std::clamp(
            environment.particleDensityScale,
            0.25f,
            1.0f);
    mainBasePush.waterFogScale =
        projectionFocal;
    mainBasePush.reflectionPlaneX =
        mainPlaneNx;
    mainBasePush.reflectionPlaneY =
        mainPlaneNy;
    mainBasePush.reflectionPlaneZ =
        mainPlaneNz;
    mainBasePush.reflectionPlaneDistance =
        mainPlaneD;

    const auto drawPrimitive = [&](
        float tx,
        float ty,
        float tz,
        float sx,
        float sy,
        float sz,
        float materialId,
        float shapeId,
        float objectYawRadians,
        float objectPitchRadians,
        std::uint32_t vertexCount) noexcept {
        PushConstants push =
            mainBasePush;
        push.materialId =
            materialId;

        push.translationX = tx;
        push.translationY = ty;
        push.translationZ = tz;
        push.translationPadding =
            std::isfinite(objectYawRadians)
            ? objectYawRadians
            : 0.0f;

        push.scaleX = sx;
        push.scaleY = sy;
        push.scaleZ = sz;
        push.scalePadding =
            std::isfinite(shapeId)
            ? shapeId
            : 0.0f;
        push.cameraPadding1 =
            std::isfinite(objectPitchRadians)
            ? objectPitchRadians
            : 0.0f;

        const bool reflectiveMaterial =
            materialId == 13.0f ||
            materialId == 14.0f;
        if (!reflectiveMaterial) {
            push.reflectionPlaneX =
                mainCameraCosYaw;
            push.reflectionPlaneY =
                mainCameraSinYaw;
            push.reflectionPlaneZ =
                mainCameraCosPitch;
            push.reflectionPlaneDistance =
                mainCameraSinPitch;
        }

        vkCmdPushConstants(
            command,
            pipelineLayout_,
            VK_SHADER_STAGE_VERTEX_BIT |
                VK_SHADER_STAGE_FRAGMENT_BIT,
            0,
            static_cast<std::uint32_t>(
                sizeof(PushConstants)),
            &push);

        vkCmdDraw(
            command,
            std::max<std::uint32_t>(
                vertexCount,
                3U),
            1,
            0,
            0);
    };

    const auto drawBox = [&](
        float tx,
        float ty,
        float tz,
        float sx,
        float sy,
        float sz,
        float materialId) noexcept {
        drawPrimitive(
            tx,
            ty,
            tz,
            sx,
            sy,
            sz,
            materialId,
            0.0f,
            0.0f,
            0.0f,
            36U);
    };

    const auto drawRounded = [&](
        float tx,
        float ty,
        float tz,
        float sx,
        float sy,
        float sz,
        float materialId,
        float yawRadians,
        float pitchRadians) noexcept {
        drawPrimitive(
            tx,
            ty,
            tz,
            sx,
            sy,
            sz,
            materialId,
            1.0f,
            yawRadians,
            pitchRadians,
            288U);
    };

    const auto drawCylinder = [&](
        float tx,
        float ty,
        float tz,
        float sx,
        float sy,
        float sz,
        float materialId,
        float yawRadians,
        float pitchRadians) noexcept {
        drawPrimitive(
            tx,
            ty,
            tz,
            sx,
            sy,
            sz,
            materialId,
            2.0f,
            yawRadians,
            pitchRadians,
            144U);
    };

    // Main world geometry is now submitted from MapDefinition rather than
    // being duplicated inside the renderer. Map authors can change geometry
    // without touching Vulkan command recording.
    const std::size_t visibleMapBoxCount =
        sanctumMesh_.ready()
        ? 0U
        : std::min(
              scene.mapBoxCount,
              scene.mapBoxes.size());

    for (std::size_t i = 0;
         i < visibleMapBoxCount;
         ++i) {
        const auto& box = scene.mapBoxes[i];

        if (!box.visible) {
            continue;
        }

        drawBox(
            box.x,
            box.y,
            box.z,
            box.scaleX,
            box.scaleY,
            box.scaleZ,
            box.materialId);
    }

    const std::size_t visibleDoorCount =
        std::min(
            scene.doorCount,
            scene.doors.size());

    for (std::size_t doorIndex = 0;
         doorIndex < visibleDoorCount;
         ++doorIndex) {
        const auto& door = scene.doors[doorIndex];

        if (!door.visible) {
            continue;
        }

        const float rawProgress =
            std::clamp(door.openProgress, 0.0f, 1.0f);
        const float eased =
            rawProgress * rawProgress *
            (3.0f - 2.0f * rawProgress);
        const float swingSign =
            (door.id & 1U) != 0U ? -1.0f : 1.0f;
        const float angle =
            swingSign * eased * 1.658062789f;

        const bool thinX = door.halfX <= door.halfZ;
        float centerX = door.x;
        float centerZ = door.z;

        if (thinX) {
            const float hingeZ = door.z - door.halfZ;
            centerX =
                door.x + std::sin(angle) * door.halfZ;
            centerZ =
                hingeZ + std::cos(angle) * door.halfZ;
        } else {
            const float hingeX = door.x - door.halfX;
            centerX =
                hingeX + std::cos(angle) * door.halfX;
            centerZ =
                door.z - std::sin(angle) * door.halfX;
        }

        // Dark timber leaf. Keep it independent of the HQ scan so the same
        // authored blocker drives collision and visible motion.
        drawPrimitive(
            centerX,
            door.y,
            centerZ,
            door.halfX / 0.75f,
            door.halfY / 0.75f,
            door.halfZ / 0.75f,
            5.0f,
            0.0f,
            angle,
            0.0f,
            36U);

        // Small metal handle follows the free edge of the swinging leaf.
        float handleX = centerX;
        float handleZ = centerZ;
        if (thinX) {
            const float local =
                door.halfZ * 0.68f;
            handleX =
                centerX +
                std::sin(angle) * local;
            handleZ =
                centerZ +
                std::cos(angle) * local;
        } else {
            const float local =
                door.halfX * 0.68f;
            handleX =
                centerX +
                std::cos(angle) * local;
            handleZ =
                centerZ -
                std::sin(angle) * local;
        }

        drawRounded(
            handleX,
            door.y + door.halfY * 0.05f,
            handleZ,
            0.055f,
            0.065f,
            0.055f,
            10.0f,
            angle,
            0.0f);
    }

    const std::size_t visibleWindowCount =
        std::min(
            scene.windowCount,
            scene.windows.size());

    if (sanctumMesh_.ready() &&
        visibleWindowCount > 0U) {
        static bool loggedDynamicBarricades = false;
        if (!loggedDynamicBarricades) {
            __android_log_print(
                ANDROID_LOG_INFO,
                kTag,
                "XZIEL_SANCTUM_DYNAMIC_BARRICADES_READY windows=%zu",
                visibleWindowCount);
            loggedDynamicBarricades = true;
        }
    }

    for (std::size_t windowIndex = 0;
         windowIndex < visibleWindowCount;
         ++windowIndex) {
        const auto& window =
            scene.windows[windowIndex];

        if (!window.visible ||
            window.maximumPlanks == 0U) {
            continue;
        }

        const std::uint32_t plankCount =
            std::min(
                window.intactPlanks,
                window.maximumPlanks);

        const bool thinX =
            window.halfWidth <= window.halfDepth;

        if (sanctumMesh_.ready()) {
            // The scan has genuine missing pixels around parts of the Gothic
            // tracery. Window blockers are fitted to gameplay openings, but
            // their thin axis does not encode which side of the original wall
            // is visually exposed. Draw two slightly oversized, shallow dark
            // backplanes on opposite sides of that axis. The scan itself still
            // wins depth on intact stone, while any real hole sees a dark
            // recess instead of the clear-color void. This remains render-only:
            // collision and barricade state are untouched.
            constexpr float recessHalfThickness = 0.055f;
            constexpr float recessOffset = 0.18f;
            constexpr float recessExtentScale = 1.58f;

            for (float recessSide : {-1.0f, 1.0f}) {
                const float recessX =
                    window.x +
                    (thinX
                        ? recessSide * recessOffset
                        : 0.0f);
                const float recessZ =
                    window.z +
                    (thinX
                        ? 0.0f
                        : recessSide * recessOffset);

                drawBox(
                    recessX,
                    window.y,
                    recessZ,
                    thinX
                        ? recessHalfThickness / 0.75f
                        : (window.halfWidth * recessExtentScale) / 0.75f,
                    (window.halfHeight * recessExtentScale) / 0.75f,
                    thinX
                        ? (window.halfDepth * recessExtentScale) / 0.75f
                        : recessHalfThickness / 0.75f,
                    7.0f);
            }
        }

        for (std::uint32_t plankIndex = 0U;
             plankIndex < plankCount;
             ++plankIndex) {
            const float alpha =
                (static_cast<float>(plankIndex) + 0.5f) /
                static_cast<float>(window.maximumPlanks);

            const int staggerIndex =
                static_cast<int>(
                    (windowIndex * 11U +
                     plankIndex * 7U) % 5U) - 2;

            const float plankY =
                window.y -
                window.halfHeight +
                alpha * window.halfHeight * 2.0f +
                static_cast<float>(staggerIndex) * 0.025f;

            // Gameplay-authoritative dark wood plank. Rendering from
            // intactPlanks means tearing/rebuilding immediately changes the
            // visible barricade rather than leaving baked dressing behind.
            drawBox(
                window.x,
                plankY,
                window.z,
                window.halfWidth / 0.75f,
                0.075f,
                window.halfDepth / 0.75f,
                5.0f);

        }

        // Keep fastener detail bounded on mobile: two visible metal caps per
        // barricade instead of two extra draws for every plank. The wood state
        // remains fully gameplay-authoritative while worst-case procedural
        // window draws stay near 224 rather than ~504.
        if (plankCount > 0U) {
            const std::uint32_t fastenerPlank =
                std::min(
                    plankCount - 1U,
                    window.maximumPlanks / 2U);

            const float fastenerAlpha =
                (static_cast<float>(fastenerPlank) + 0.5f) /
                static_cast<float>(window.maximumPlanks);

            const float fastenerY =
                window.y -
                window.halfHeight +
                fastenerAlpha * window.halfHeight * 2.0f;

            for (int nailSide : {-1, 1}) {
                float nailX = window.x;
                float nailZ = window.z;

                if (thinX) {
                    nailX += 0.055f;
                    nailZ +=
                        static_cast<float>(nailSide) *
                        window.halfDepth * 0.58f;
                } else {
                    nailX +=
                        static_cast<float>(nailSide) *
                        window.halfWidth * 0.58f;
                    nailZ += 0.055f;
                }

                drawRounded(
                    nailX,
                    fastenerY,
                    nailZ,
                    0.035f,
                    0.035f,
                    0.035f,
                    10.0f,
                    0.0f,
                    0.0f);
            }
        }
    }

    if (!sanctumMesh_.ready()) {
        const float prototypeDoorOpen =
            std::clamp(
                scene.doorOpenAlpha,
                0.0f,
                1.0f);

        drawBox(
            -2.88f,
            -0.12f,
            1.57f,
            0.12f,
            1.52f,
            0.20f,
            1.0f);

        drawBox(
            2.88f,
            -0.12f,
            1.57f,
            0.12f,
            1.52f,
            0.20f,
            1.0f);

        drawBox(
            0.0f,
            1.34f,
            1.57f,
            3.0f,
            0.10f,
            0.20f,
            1.0f);

        drawBox(
            0.0f,
            -0.18f +
                prototypeDoorOpen *
                    3.05f,
            1.57f,
            2.72f,
            1.32f,
            0.10f,
            prototypeDoorOpen >
                0.01f
                ? 7.0f
                : 8.0f);
    }

    if (scene.interactionVisible) {
        drawBox(
            scene.interactionX,
            scene.interactionY,
            scene.interactionZ,
            0.18f,
            0.30f,
            0.12f,
            scene.interactionActive
                ? 7.0f
                : 8.0f);

        drawBox(
            scene.interactionX,
            scene.interactionY + 0.30f,
            scene.interactionZ - 0.02f,
            0.09f,
            0.055f,
            0.035f,
            scene.interactionActive
                ? 7.0f
                : 8.0f);
    }

    const std::size_t visibleZombieCount =
        std::min(
            scene.zombieCount,
            scene.zombies.size());

    for (std::size_t zombieIndex = 0;
         zombieIndex < visibleZombieCount;
         ++zombieIndex) {
        const auto& zombieState =
            scene.zombies[
                zombieIndex];

        if (!zombieState.visible) {
            continue;
        }

        const float stride =
            std::sin(
                zombieState.stridePhase *
                6.28318530718f);

        const float zombieYaw =
            zombieState.yawRadians;

        const float forwardX =
            std::sin(zombieYaw);
        const float forwardZ =
            std::cos(zombieYaw);
        const float rightX =
            std::cos(zombieYaw);
        const float rightZ =
            -std::sin(zombieYaw);

        const float staggerSide =
            zombieState.staggered
            ? std::sin(
                  safeTime *
                  38.0f +
                  static_cast<float>(
                      zombieIndex)) *
                  0.045f
            : 0.0f;

        const float attackLunge =
            zombieState.attack
            ? 0.16f
            : 0.0f;

        // Apply all presentation offsets in the actor's local basis. The old
        // proxy placed limbs on global +/-X and lunged toward global -Z, so a
        // zombie could move toward the player while its body read backwards.
        const float zombieX =
            zombieState.x +
            rightX * staggerSide +
            forwardX * attackLunge;

        const float zombieY =
            zombieState.y;

        const float zombieZ =
            zombieState.z +
            rightZ * staggerSide +
            forwardZ * attackLunge;

        const auto anchor = [&](
            float side,
            float up,
            float forward) noexcept {
            return std::array<float, 3>{
                zombieX +
                    rightX * side +
                    forwardX * forward,
                zombieY + up,
                zombieZ +
                    rightZ * side +
                    forwardZ * forward,
            };
        };

        // Ground contact follows each zombie's actual navigation-floor Y.
        drawBox(
            zombieX,
            zombieY + 0.012f,
            zombieZ,
            0.34f,
            0.008f,
            0.24f,
            7.0f);

        const float lean =
            zombieState.staggered
            ? staggerSide * 4.0f
            : (zombieState.attack ? -0.10f : 0.035f);

        // Tattered torso + hips.
        drawRounded(
            zombieX,
            zombieY + 1.02f,
            zombieZ,
            0.30f,
            0.48f,
            0.20f,
            18.0f,
            zombieYaw,
            lean);

        drawRounded(
            zombieX,
            zombieY + 0.66f,
            zombieZ - 0.01f,
            0.27f,
            0.20f,
            0.21f,
            18.0f,
            zombieYaw,
            lean * 0.55f);

        // Neck and head. A small forward jaw plus eye sockets make facing
        // direction readable even though this is still generated geometry.
        const auto neck =
            anchor(
                0.0f,
                1.46f,
                0.0f);

        drawCylinder(
            neck[0],
            neck[1],
            neck[2],
            0.085f,
            0.085f,
            0.12f,
            17.0f,
            zombieYaw,
            1.570796327f);

        const auto head =
            anchor(
                0.0f,
                1.68f,
                0.015f);

        drawRounded(
            head[0],
            head[1],
            head[2],
            0.18f,
            0.225f,
            0.17f,
            17.0f,
            zombieYaw,
            zombieState.attack
                ? -0.10f
                : 0.045f);

        const auto jaw =
            anchor(
                0.0f,
                1.58f,
                0.155f);

        drawRounded(
            jaw[0],
            jaw[1],
            jaw[2],
            0.115f,
            0.075f,
            0.075f,
            17.0f,
            zombieYaw,
            -0.08f);

        for (float eyeSide : {-0.060f, 0.060f}) {
            const auto eye =
                anchor(
                    eyeSide,
                    1.72f,
                    0.165f);

            drawRounded(
                eye[0],
                eye[1],
                eye[2],
                0.030f,
                0.028f,
                0.025f,
                7.0f,
                zombieYaw,
                0.0f);
        }

        const float legSwing =
            stride * 0.42f;

        const float armSwing =
            zombieState.attack
            ? 0.0f
            : -legSwing * 0.72f;

        // Arms anchor in local right/forward space, not global X/Z.
        for (int sideSign : {-1, 1}) {
            const float side =
                static_cast<float>(
                    sideSign);

            const float shoulderSide =
                side * 0.315f;

            const float armForward =
                zombieState.attack
                ? 0.27f
                : side * stride * 0.025f;

            const float armUp =
                zombieState.attack
                ? 1.23f
                : 1.08f;

            const auto arm =
                anchor(
                    shoulderSide,
                    armUp,
                    armForward);

            const float attackSpread =
                side * 0.08f;

            drawCylinder(
                arm[0],
                arm[1],
                arm[2],
                0.100f,
                0.095f,
                0.36f,
                17.0f,
                zombieYaw + attackSpread,
                zombieState.attack
                    ? 0.18f
                    : 1.48f +
                        side *
                        armSwing *
                        0.52f);

            const auto sleeve =
                anchor(
                    side * 0.285f,
                    zombieState.attack
                        ? 1.17f
                        : 1.21f,
                    zombieState.attack
                        ? 0.04f
                        : 0.0f);

            drawRounded(
                sleeve[0],
                sleeve[1],
                sleeve[2],
                0.135f,
                0.19f,
                0.13f,
                18.0f,
                zombieYaw,
                side * armSwing * 0.25f);
        }

        // Legs and feet use the same actor-local basis, so stride remains
        // visually aligned with the direction the zombie is actually moving.
        for (int sideSign : {-1, 1}) {
            const float side =
                static_cast<float>(
                    sideSign);

            const float step =
                side * legSwing;

            const auto leg =
                anchor(
                    side * 0.145f,
                    0.39f,
                    step * 0.055f);

            drawCylinder(
                leg[0],
                leg[1],
                leg[2],
                0.115f,
                0.105f,
                0.37f,
                18.0f,
                zombieYaw,
                1.570796327f +
                    step * 0.52f);

            const auto foot =
                anchor(
                    side * 0.145f,
                    0.095f,
                    0.11f +
                        step * 0.095f);

            drawRounded(
                foot[0],
                foot[1],
                foot[2],
                0.135f,
                0.080f,
                0.21f,
                18.0f,
                zombieYaw,
                0.04f);
        }

        if (zombieState.healthRatio <
            0.70f) {
            const auto wound =
                anchor(
                    0.14f,
                    1.22f,
                    0.205f);

            drawRounded(
                wound[0],
                wound[1],
                wound[2],
                0.085f,
                0.15f,
                0.032f,
                6.0f,
                zombieYaw,
                0.0f);
        }
    }

    const float impactAlpha =
        std::clamp(
            scene.impactAlpha,
            0.0f,
            1.0f);

    if (impactAlpha > 0.001f) {
        const float impactSize =
            scene.impactCritical
            ? 0.12f
            : 0.075f;

        drawBox(
            scene.impactX,
            scene.impactY,
            scene.impactZ,
            impactSize,
            impactSize,
            impactSize,
            6.0f);

        drawBox(
            scene.impactX +
                0.08f * impactAlpha,
            scene.impactY +
                0.05f * impactAlpha,
            scene.impactZ -
                0.04f * impactAlpha,
            impactSize * 0.55f,
            impactSize * 0.55f,
            impactSize * 0.55f,
            6.0f);

        drawBox(
            scene.impactX -
                0.07f * impactAlpha,
            scene.impactY +
                0.02f * impactAlpha,
            scene.impactZ +
                0.05f * impactAlpha,
            impactSize * 0.42f,
            impactSize * 0.42f,
            impactSize * 0.42f,
            6.0f);
    }

    const float rainForSplashes =
        std::clamp(
            environment.rainIntensity *
                environment.particleDensityScale,
            0.0f,
            1.0f);

    if (rainForSplashes > 0.08f) {
        constexpr int kPrototypeSplashCount = 7;

        for (int splashIndex = 0;
             splashIndex < kPrototypeSplashCount;
             ++splashIndex) {
            const float seed =
                static_cast<float>(
                    splashIndex);

            const float cycle =
                std::fmod(
                    safeTime *
                        (1.7f +
                         rainForSplashes *
                             1.4f) +
                    seed *
                        0.173f,
                    1.0f);

            const float x =
                -2.35f +
                std::fmod(
                    seed *
                        1.381f,
                    4.70f);

            const float z =
                -2.80f +
                std::fmod(
                    seed *
                        1.917f,
                    5.70f);

            const float radius =
                0.025f +
                cycle *
                    0.12f;

            if (cycle < 0.72f) {
                drawBox(
                    x,
                    -1.455f,
                    z,
                    radius,
                    0.006f,
                    radius,
                    8.0f);
            }
        }
    }

    const float decapAlpha =
        std::clamp(
            scene.decapAlpha,
            0.0f,
            1.0f);

    if (decapAlpha > 0.001f) {
        const float progress =
            1.0f -
            decapAlpha;

        const float ballisticRise =
            std::sin(
                progress *
                3.14159265358979323846f) *
            0.92f;

        const float travel =
            progress *
            0.95f;

        const float headX =
            scene.decapOriginX +
            scene.decapDirectionX *
                travel +
            std::sin(
                progress *
                11.0f) *
                0.08f;

        const float headY =
            scene.decapOriginY +
            ballisticRise -
            progress *
                0.18f;

        const float headZ =
            scene.decapOriginZ +
            scene.decapDirectionZ *
                travel;

        drawBox(
            headX,
            headY,
            headZ,
            0.18f,
            0.18f,
            0.18f,
            5.0f);

        drawBox(
            headX,
            headY - 0.10f,
            headZ - 0.05f,
            0.10f,
            0.045f,
            0.10f,
            6.0f);
    }

    if (!kImportedWeaponViewmodelEnabled ||
        !weaponMesh_.ready()) {
        const float weaponAds =
            std::clamp(
                hud.weaponAdsAlpha,
                0.0f,
                1.0f);
    
        const float weaponReload =
            std::clamp(
                hud.weaponReloadAlpha,
                0.0f,
                1.0f);
    
        const float weaponFire =
            std::clamp(
                hud.weaponFireAlpha,
                0.0f,
                1.0f);
    
        const float viewmodelLowering =
            std::clamp(
                hud.viewmodelLowering,
                0.0f,
                1.0f);
    
        const float reloadArc =
            std::sin(
                weaponReload *
                3.14159265358979323846f);
    
        const float weaponX =
            0.66f *
                (1.0f - weaponAds) +
            0.035f *
                weaponAds +
            0.10f *
                viewmodelLowering;
    
        const float weaponY =
            -0.78f +
            0.18f *
                weaponAds -
            0.30f *
                reloadArc -
            0.44f *
                viewmodelLowering;
    
        const float weaponZ =
            1.34f -
            0.18f *
                weaponAds +
            0.10f *
                reloadArc +
            0.10f *
                viewmodelLowering;
    
        // Native first-person rifle blockout. Keep this renderer-owned until a
        // skinned GLB viewmodel path is production-ready, but make the current
        // Android build read like a real firearm instead of one oversized cube.
        // Materials 10/15/16 are gunmetal, worn furniture and matte polymer.
        const float fireKick =
            weaponFire * 0.11f;
    
        const float rifleY =
            weaponY -
            weaponFire * 0.025f;
    
        const float rifleZ =
            weaponZ -
            fireKick;
    
        // Buttstock + receiver.
        drawPrimitive(
            weaponX + 0.015f,
            rifleY - 0.005f,
            rifleZ - 0.54f,
            0.27f,
            0.17f,
            0.44f,
            15.0f,
            0.0f,
            0.0f,
            -0.05f,
            36U);
    
        drawBox(
            weaponX,
            rifleY,
            rifleZ - 0.05f,
            0.255f,
            0.165f,
            0.39f,
            10.0f);
    
        drawBox(
            weaponX,
            rifleY + 0.125f,
            rifleZ - 0.02f,
            0.205f,
            0.075f,
            0.31f,
            16.0f);
    
        // Forward furniture and true round barrel remove the old rectangular
        // silhouette that dominated the bottom-right of the screen.
        drawBox(
            weaponX + 0.004f,
            rifleY - 0.005f,
            rifleZ + 0.43f,
            0.22f,
            0.135f,
            0.34f,
            15.0f);
    
        drawCylinder(
            weaponX + 0.004f,
            rifleY + 0.035f,
            rifleZ + 0.94f,
            0.055f,
            0.055f,
            0.54f,
            10.0f,
            0.0f,
            0.0f);
    
        drawCylinder(
            weaponX + 0.004f,
            rifleY + 0.035f,
            rifleZ + 1.38f,
            0.078f,
            0.078f,
            0.13f,
            16.0f,
            0.0f,
            0.0f);
    
        // Magazine and pistol grip are independently tilted visual pieces.
        drawCylinder(
            weaponX - 0.010f,
            rifleY - 0.245f -
                reloadArc * 0.10f,
            rifleZ + 0.04f +
                reloadArc * 0.10f,
            0.125f,
            0.082f,
            0.30f,
            16.0f,
            0.0f,
            -1.00f +
                reloadArc * 0.30f);
    
        drawCylinder(
            weaponX + 0.015f,
            rifleY - 0.225f,
            rifleZ - 0.27f,
            0.090f,
            0.078f,
            0.22f,
            16.0f,
            0.0f,
            -0.88f);
    
        // Rear rail plus front/rear iron sights. These small layers are cheap but
        // give ADS a readable centerline instead of a featureless slab.
        drawBox(
            weaponX,
            rifleY + 0.205f,
            rifleZ - 0.04f,
            0.13f,
            0.025f,
            0.28f,
            10.0f);
    
        drawCylinder(
            weaponX,
            rifleY + 0.265f,
            rifleZ - 0.19f,
            0.032f,
            0.032f,
            0.075f,
            10.0f,
            0.0f,
            1.570796327f);
    
        drawCylinder(
            weaponX + 0.004f,
            rifleY + 0.205f,
            rifleZ + 0.75f,
            0.028f,
            0.028f,
            0.095f,
            10.0f,
            0.0f,
            1.570796327f);
    
        // Rounded gloves/forearms retain the existing reload motion but stop
        // reading as rigid cubes.
        drawRounded(
            weaponX + 0.215f,
            rifleY - 0.115f -
                reloadArc * 0.045f,
            rifleZ - 0.17f +
                reloadArc * 0.10f,
            0.14f,
            0.12f,
            0.24f,
            12.0f,
            -0.12f,
            0.30f);
    
        drawCylinder(
            weaponX + 0.30f,
            rifleY - 0.245f,
            rifleZ - 0.40f,
            0.12f,
            0.105f,
            0.32f,
            12.0f,
            0.0f,
            -0.48f);
    
        drawRounded(
            weaponX - 0.18f -
                reloadArc * 0.10f,
            rifleY - 0.055f -
                reloadArc * 0.12f,
            rifleZ + 0.35f,
            0.13f,
            0.11f,
            0.21f,
            12.0f,
            0.10f,
            -0.18f);
    
        drawCylinder(
            weaponX - 0.27f -
                reloadArc * 0.10f,
            rifleY - 0.18f -
                reloadArc * 0.10f,
            rifleZ + 0.16f,
            0.105f,
            0.095f,
            0.28f,
            12.0f,
            0.0f,
            -0.55f);
    
        if (weaponFire > 0.01f) {
            drawRounded(
                weaponX + 0.004f,
                rifleY + 0.035f,
                rifleZ + 1.53f,
                0.12f +
                    0.07f *
                    weaponFire,
                0.12f +
                    0.07f *
                    weaponFire,
                0.18f +
                    0.12f *
                    weaponFire,
                11.0f,
                0.0f,
                0.0f);
        }
    
    
    } else {
        const float fire =
            std::clamp(
                hud.weaponFireAlpha,
                0.0f,
                1.0f);

        if (fire > 0.01f) {
            const float ads =
                std::clamp(
                    hud.weaponAdsAlpha,
                    0.0f,
                    1.0f);

            drawRounded(
                0.235f * (1.0f - ads) +
                    0.004f * ads,
                -0.095f +
                    0.08f * ads,
                1.02f -
                    0.07f * fire,
                0.10f + 0.06f * fire,
                0.10f + 0.06f * fire,
                0.17f + 0.10f * fire,
                11.0f,
                0.0f,
                0.0f);
        }
    }

    vkCmdEndRenderPass(command);

    if (gpuTimestampQueryPool_ != VK_NULL_HANDLE &&
        frameSlot < kFramesInFlight) {
        const std::uint32_t queryBase =
            frameSlot *
            kGpuTimestampQueriesPerFrame;

        vkCmdWriteTimestamp(
            command,
            VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
            gpuTimestampQueryPool_,
            queryBase + 2U);
    }

    if (uiPipeline_ == VK_NULL_HANDLE ||
        uiPipelineLayout_ == VK_NULL_HANDLE ||
        sceneCompositePipeline_ == VK_NULL_HANDLE ||
        sceneCompositePipelineLayout_ == VK_NULL_HANDLE ||
        uiRenderPass_ == VK_NULL_HANDLE ||
        imageIndex >= uiFramebuffers_.size() ||
        imageIndex >= sceneCompositeDescriptorSets_.size()) {
        logError("native UI/composite pipeline missing");
        return false;
    }

    VkClearValue uiClear{};
    uiClear.color.float32[0] = 0.0f;
    uiClear.color.float32[1] = 0.0f;
    uiClear.color.float32[2] = 0.0f;
    uiClear.color.float32[3] = 1.0f;

    VkRenderPassBeginInfo uiRender{
        VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO
    };
    uiRender.renderPass = uiRenderPass_;
    uiRender.framebuffer = uiFramebuffers_[imageIndex];
    uiRender.renderArea.extent = swapchainExtent_;
    uiRender.clearValueCount = 1U;
    uiRender.pClearValues = &uiClear;

    vkCmdBeginRenderPass(
        command,
        &uiRender,
        VK_SUBPASS_CONTENTS_INLINE);

    vkCmdBindPipeline(
        command,
        VK_PIPELINE_BIND_POINT_GRAPHICS,
        sceneCompositePipeline_);
    vkCmdBindDescriptorSets(
        command,
        VK_PIPELINE_BIND_POINT_GRAPHICS,
        sceneCompositePipelineLayout_,
        0U,
        1U,
        &sceneCompositeDescriptorSets_[imageIndex],
        0U,
        nullptr);
    vkCmdDraw(
        command,
        3U,
        1U,
        0U,
        0U);

    const VkDeviceSize uiBatchFrameBytes =
        static_cast<VkDeviceSize>(
            sizeof(UiBatchVertex)) *
        kUiBatchVerticesPerFrame;
    const VkDeviceSize uiBatchFrameOffset =
        uiBatchFrameBytes *
        frameSlot;

    auto* uiBatchFrameVertices =
        uiBatchMapped_ != nullptr
        ? static_cast<UiBatchVertex*>(
              uiBatchMapped_) +
              static_cast<std::size_t>(
                  frameSlot) *
                  kUiBatchVerticesPerFrame
        : nullptr;

    std::uint32_t uiBatchVertexCursor = 0U;
    std::uint32_t uiBatchPendingStart = 0U;
    std::uint32_t uiBatchPendingCount = 0U;
    std::uint32_t uiLogicalPrimitiveDraws = 0U;
    std::uint32_t uiBatchSubmissions = 0U;
    std::uint32_t uiFallbackPrimitiveDraws = 0U;
    std::uint32_t uiDigitDraws = 0U;
    std::uint32_t uiDigitSegments = 0U;

    const auto flushUiPrimitiveBatch = [&]() noexcept {
        if (uiBatchPendingCount == 0U) {
            return;
        }

        vkCmdBindPipeline(
            command,
            VK_PIPELINE_BIND_POINT_GRAPHICS,
            uiBatchPipeline_);

        const VkBuffer vertexBuffer =
            uiBatchVertexBuffer_;
        const VkDeviceSize vertexOffset =
            uiBatchFrameOffset;

        vkCmdBindVertexBuffers(
            command,
            0U,
            1U,
            &vertexBuffer,
            &vertexOffset);

        vkCmdDraw(
            command,
            uiBatchPendingCount,
            1U,
            uiBatchPendingStart,
            0U);

        ++uiBatchSubmissions;
        uiBatchPendingCount = 0U;
        uiBatchPendingStart =
            uiBatchVertexCursor;
    };

    const float viewportWidth =
        static_cast<float>(
            std::max(
                swapchainExtent_.width,
                1U));

    const float viewportHeight =
        static_cast<float>(
            std::max(
                swapchainExtent_.height,
                1U));

    const float minViewport =
        std::min(
            viewportWidth,
            viewportHeight);

    const auto drawUiPrimitive = [&](
        float centerXNormalized,
        float centerYNormalized,
        float halfWidthNormalized,
        float halfHeightNormalized,
        float red,
        float green,
        float blue,
        float alpha,
        float shape,
        float ringWidth) noexcept {
        UiPushConstants ui{};

        ui.centerX =
            std::clamp(
                centerXNormalized,
                0.0f,
                1.0f) *
                2.0f -
            1.0f;

        ui.centerY =
            1.0f -
            std::clamp(
                centerYNormalized,
                0.0f,
                1.0f) *
                2.0f;

        ui.halfWidth =
            std::max(
                halfWidthNormalized,
                0.0005f) *
            2.0f;

        ui.halfHeight =
            std::max(
                halfHeightNormalized,
                0.0005f) *
            2.0f;

        ui.colorR =
            std::clamp(
                red,
                0.0f,
                1.0f);

        ui.colorG =
            std::clamp(
                green,
                0.0f,
                1.0f);

        ui.colorB =
            std::clamp(
                blue,
                0.0f,
                1.0f);

        ui.colorA =
            std::clamp(
                alpha,
                0.0f,
                1.0f);

        ui.shape = shape;
        ui.ringWidth = ringWidth;

        ++uiLogicalPrimitiveDraws;

        const bool batchReady =
            uiBatchPipeline_ != VK_NULL_HANDLE &&
            uiBatchVertexBuffer_ != VK_NULL_HANDLE &&
            uiBatchFrameVertices != nullptr;

        if (batchReady) {
            if (uiBatchVertexCursor +
                    kUiBatchVerticesPerPrimitive >
                kUiBatchVerticesPerFrame) {
                flushUiPrimitiveBatch();
            }

            if (uiBatchVertexCursor +
                    kUiBatchVerticesPerPrimitive <=
                kUiBatchVerticesPerFrame) {
                if (uiBatchPendingCount == 0U) {
                    uiBatchPendingStart =
                        uiBatchVertexCursor;
                }

                for (std::uint32_t vertexIndex = 0U;
                     vertexIndex <
                         kUiBatchVerticesPerPrimitive;
                     ++vertexIndex) {
                    const auto& local =
                        kUiQuad[vertexIndex];

                    UiBatchVertex& vertex =
                        uiBatchFrameVertices[
                            uiBatchVertexCursor +
                            vertexIndex];

                    vertex.positionX =
                        ui.centerX +
                        local[0] *
                            ui.halfWidth;
                    vertex.positionY =
                        ui.centerY +
                        local[1] *
                            ui.halfHeight;
                    vertex.localX = local[0];
                    vertex.localY = local[1];
                    vertex.colorR = ui.colorR;
                    vertex.colorG = ui.colorG;
                    vertex.colorB = ui.colorB;
                    vertex.colorA = ui.colorA;
                    vertex.shape = ui.shape;
                    vertex.ringWidth =
                        ui.ringWidth;
                }

                uiBatchVertexCursor +=
                    kUiBatchVerticesPerPrimitive;
                uiBatchPendingCount +=
                    kUiBatchVerticesPerPrimitive;
                return;
            }
        }

        vkCmdBindPipeline(
            command,
            VK_PIPELINE_BIND_POINT_GRAPHICS,
            uiPipeline_);
        vkCmdPushConstants(
            command,
            uiPipelineLayout_,
            VK_SHADER_STAGE_VERTEX_BIT |
                VK_SHADER_STAGE_FRAGMENT_BIT,
            0,
            static_cast<std::uint32_t>(
                sizeof(UiPushConstants)),
            &ui);

        vkCmdDraw(
            command,
            6,
            1,
            0,
            0);
        ++uiFallbackPrimitiveDraws;
    };

    const auto drawUiCircle = [&](
        float centerXNormalized,
        float centerYNormalized,
        float radiusOfShortSide,
        float red,
        float green,
        float blue,
        float alpha,
        bool ring,
        float ringWidth = 0.18f) noexcept {
        const float radiusPixels =
            std::max(
                radiusOfShortSide,
                0.002f) *
            minViewport;

        drawUiPrimitive(
            centerXNormalized,
            centerYNormalized,
            radiusPixels /
                viewportWidth,
            radiusPixels /
                viewportHeight,
            red,
            green,
            blue,
            alpha,
            ring ? 2.0f : 1.0f,
            ringWidth);
    };

    static constexpr std::array<std::uint8_t, 10>
        kDigitMasks{{
            0x3FU,
            0x06U,
            0x5BU,
            0x4FU,
            0x66U,
            0x6DU,
            0x7DU,
            0x07U,
            0x7FU,
            0x6FU,
        }};

    const auto drawSevenSegmentDigit = [&](
        int digit,
        float centerX,
        float centerY,
        float scale,
        float alpha) noexcept {
        if (digit < 0 || digit > 9) {
            return;
        }

        const std::uint8_t digitMask =
            kDigitMasks[
                static_cast<std::size_t>(
                    digit)];

        const float digitScale =
            std::max(
                scale,
                0.01f);

        const float digitGreen =
            0.58f +
            0.20f *
                std::clamp(
                    hud.scorePulseAlpha,
                    0.0f,
                    1.0f);

        constexpr float xStep = 0.0168f;
        constexpr float yStep = 0.0160f;
        constexpr float horizontalHalfX = 0.0156f;
        constexpr float horizontalHalfY = 0.0025f;
        constexpr float verticalHalfX = 0.0024f;
        constexpr float verticalHalfY = 0.0124f;

        for (int segmentIndex = 0;
             segmentIndex < 7;
             ++segmentIndex) {
            std::uint8_t segmentBit = 0U;
            float offsetClipX = 0.0f;
            float offsetClipY = 0.0f;
            float halfClipX = 0.0f;
            float halfClipY = 0.0f;

            switch (segmentIndex) {
                case 0:
                    segmentBit = 0x01U;
                    offsetClipY = 2.0f * yStep;
                    halfClipX = horizontalHalfX;
                    halfClipY = horizontalHalfY;
                    break;
                case 1:
                    segmentBit = 0x02U;
                    offsetClipX = xStep;
                    offsetClipY = yStep;
                    halfClipX = verticalHalfX;
                    halfClipY = verticalHalfY;
                    break;
                case 2:
                    segmentBit = 0x04U;
                    offsetClipX = xStep;
                    offsetClipY = -yStep;
                    halfClipX = verticalHalfX;
                    halfClipY = verticalHalfY;
                    break;
                case 3:
                    segmentBit = 0x08U;
                    offsetClipY = -2.0f * yStep;
                    halfClipX = horizontalHalfX;
                    halfClipY = horizontalHalfY;
                    break;
                case 4:
                    segmentBit = 0x10U;
                    offsetClipX = -xStep;
                    offsetClipY = -yStep;
                    halfClipX = verticalHalfX;
                    halfClipY = verticalHalfY;
                    break;
                case 5:
                    segmentBit = 0x20U;
                    offsetClipX = -xStep;
                    offsetClipY = yStep;
                    halfClipX = verticalHalfX;
                    halfClipY = verticalHalfY;
                    break;
                default:
                    segmentBit = 0x40U;
                    halfClipX = horizontalHalfX;
                    halfClipY = horizontalHalfY;
                    break;
            }

            if ((digitMask & segmentBit) == 0U) {
                continue;
            }

            // The old digit shader authored offsets/extents in clip space.
            // drawUiPrimitive accepts normalized screen coordinates, so x
            // deltas halve while y deltas halve and invert.
            drawUiPrimitive(
                centerX +
                    offsetClipX *
                        digitScale *
                        0.5f,
                centerY -
                    offsetClipY *
                        digitScale *
                        0.5f,
                halfClipX *
                    digitScale *
                    0.5f,
                halfClipY *
                    digitScale *
                    0.5f,
                0.92f,
                digitGreen,
                0.10f,
                alpha,
                0.0f,
                0.10f);

            ++uiDigitSegments;
        }
    };

    const float rainIntensity =
        std::clamp(
            environment.rainIntensity,
            0.0f,
            1.0f);

    if (rainIntensity > 0.01f) {
        const int visibleRainStreaks =
            std::clamp(
                static_cast<int>(
                    std::lround(
                        18.0f *
                        std::clamp(
                            environment.
                                particleDensityScale,
                            0.25f,
                            1.0f))),
                5,
                18);

        for (int i = 0;
             i < visibleRainStreaks;
             ++i) {
            const float seed =
                static_cast<float>(i) *
                0.61803398875f;

            const float wrappedX =
                std::fmod(
                    seed +
                    safeTime *
                        (0.035f +
                         rainIntensity *
                             0.018f) +
                    environment.windX *
                        0.012f,
                    1.0f);

            const float normalizedX =
                wrappedX < 0.0f
                ? wrappedX + 1.0f
                : wrappedX;

            const float fall =
                std::fmod(
                    static_cast<float>(i) *
                        0.173f +
                    safeTime *
                        (0.72f +
                         0.35f *
                             rainIntensity),
                    1.18f);

            const float normalizedY =
                fall - 0.09f;

            drawUiPrimitive(
                normalizedX,
                normalizedY,
                0.0008f,
                0.022f +
                    rainIntensity *
                        0.018f,
                0.52f,
                0.72f,
                0.92f,
                0.10f +
                    rainIntensity *
                        0.22f,
                0.0f,
                0.10f);
        }
    }

    const float fogOverlay =
        std::clamp(
            environment.fogDensity *
                0.10f *
                std::clamp(
                    environment.fogQualityScale,
                    0.25f,
                    1.0f),
            0.0f,
            0.12f);

    if (fogOverlay > 0.001f) {
        drawUiPrimitive(
            0.5f,
            0.5f,
            0.5f,
            0.5f,
            0.035f,
            0.045f,
            0.065f,
            fogOverlay,
            0.0f,
            0.10f);
    }

    const float lightningOverlay =
        std::clamp(
            environment.lightningFlash *
                0.24f *
                std::clamp(
                    environment.postProcessScale,
                    0.35f,
                    1.0f),
            0.0f,
            0.30f);

    if (lightningOverlay > 0.001f) {
        drawUiPrimitive(
            0.5f,
            0.5f,
            0.5f,
            0.5f,
            0.68f,
            0.78f,
            1.0f,
            lightningOverlay,
            0.0f,
            0.10f);
    }

    std::array<int, 6> scoreDigits{};
    std::uint64_t scoreValue =
        hud.scoreTotal %
        1000000ULL;

    for (std::size_t reverseIndex = 0;
         reverseIndex <
             scoreDigits.size();
         ++reverseIndex) {
        const std::size_t index =
            scoreDigits.size() -
            1U -
            reverseIndex;

        scoreDigits[index] =
            static_cast<int>(
                scoreValue %
                10ULL);

        scoreValue /= 10ULL;
    }

    std::size_t firstVisibleDigit =
        scoreDigits.size() - 1U;

    for (std::size_t i = 0;
         i + 1U <
             scoreDigits.size();
         ++i) {
        if (scoreDigits[i] != 0) {
            firstVisibleDigit = i;
            break;
        }
    }

    const float scorePulse =
        std::clamp(
            hud.scorePulseAlpha,
            0.0f,
            1.0f);

    const float scoreScale =
        1.0f +
        scorePulse *
            0.10f;

    const float scoreAlpha =
        0.72f +
        scorePulse *
            0.26f;

    float scoreX = 0.055f;

    for (std::size_t i = firstVisibleDigit;
         i < scoreDigits.size();
         ++i) {
        drawSevenSegmentDigit(
            scoreDigits[i],
            scoreX,
            0.095f,
            scoreScale,
            scoreAlpha);

        scoreX +=
            0.022f *
            scoreScale;
    }

    const float shortToX =
        minViewport /
        viewportWidth;

    const float shortToY =
        minViewport /
        viewportHeight;

    const auto drawShortRect = [&](
        float centerX,
        float centerY,
        float halfWidthShort,
        float halfHeightShort,
        float red,
        float green,
        float blue,
        float alpha) noexcept {
        drawUiPrimitive(
            centerX,
            centerY,
            halfWidthShort * shortToX,
            halfHeightShort * shortToY,
            red,
            green,
            blue,
            alpha,
            0.0f,
            0.10f);
    };

    const auto drawActionBackplate = [&](
        float x,
        float y,
        float radius,
        bool active) noexcept {
        // Dark tactical pad with a warm yellow-green accent, matching the
        // supplied mobile shooter reference instead of the old debug rings.
        drawUiCircle(
            x,
            y,
            radius,
            0.025f,
            0.028f,
            0.030f,
            active ? 0.82f : 0.58f,
            false);
        drawUiCircle(
            x,
            y,
            radius,
            0.88f,
            0.96f,
            0.18f,
            active ? 0.96f : 0.54f,
            true,
            active ? 0.085f : 0.060f);
    };

    const auto drawCrosshairIcon = [&](
        float x,
        float y,
        float alpha) noexcept {
        drawUiCircle(
            x,
            y,
            0.025f,
            0.93f,
            0.96f,
            1.0f,
            alpha,
            true,
            0.10f);
        drawShortRect(x, y - 0.037f, 0.0022f, 0.010f, 0.93f, 0.96f, 1.0f, alpha);
        drawShortRect(x, y + 0.037f, 0.0022f, 0.010f, 0.93f, 0.96f, 1.0f, alpha);
        drawShortRect(x - 0.037f * shortToX, y, 0.010f, 0.0022f, 0.93f, 0.96f, 1.0f, alpha);
        drawShortRect(x + 0.037f * shortToX, y, 0.010f, 0.0022f, 0.93f, 0.96f, 1.0f, alpha);
    };

    const auto drawBulletIcon = [&](
        float x,
        float y,
        float alpha) noexcept {
        drawShortRect(x, y + 0.004f, 0.0060f, 0.019f, 0.98f, 0.98f, 0.98f, alpha);
        drawUiCircle(
            x,
            y - 0.018f,
            0.0061f,
            0.98f,
            0.98f,
            0.98f,
            alpha,
            false);
        drawShortRect(x, y + 0.025f, 0.0075f, 0.0030f, 1.0f, 0.94f, 0.86f, alpha);
    };

    const auto drawReloadIcon = [&](
        float x,
        float y,
        float alpha) noexcept {
        drawUiCircle(
            x,
            y,
            0.024f,
            0.96f,
            0.96f,
            0.96f,
            alpha,
            true,
            0.11f);
        // Break a small section of the ring and add a blocky arrowhead.
        drawShortRect(x + 0.020f * shortToX, y - 0.018f, 0.010f, 0.007f, 0.015f, 0.020f, 0.028f, 0.98f);
        drawShortRect(x + 0.023f * shortToX, y - 0.018f, 0.009f, 0.0025f, 0.96f, 0.96f, 0.96f, alpha);
        drawShortRect(x + 0.029f * shortToX, y - 0.011f, 0.0028f, 0.008f, 0.96f, 0.96f, 0.96f, alpha);
    };

    const auto drawJumpIcon = [&](
        float x,
        float y,
        float alpha) noexcept {
        drawUiCircle(x, y - 0.023f, 0.0072f, 0.96f, 0.98f, 1.0f, alpha, false);
        drawShortRect(x, y - 0.002f, 0.0035f, 0.013f, 0.96f, 0.98f, 1.0f, alpha);
        drawShortRect(x, y - 0.004f, 0.015f, 0.0030f, 0.96f, 0.98f, 1.0f, alpha);
        drawShortRect(x - 0.008f * shortToX, y + 0.016f, 0.0032f, 0.012f, 0.96f, 0.98f, 1.0f, alpha);
        drawShortRect(x + 0.008f * shortToX, y + 0.016f, 0.0032f, 0.012f, 0.96f, 0.98f, 1.0f, alpha);
        drawShortRect(x, y - 0.042f, 0.0024f, 0.007f, 0.96f, 0.98f, 1.0f, alpha * 0.85f);
        drawShortRect(x, y - 0.050f, 0.009f, 0.0023f, 0.96f, 0.98f, 1.0f, alpha * 0.85f);
    };

    const auto drawCrouchIcon = [&](
        float x,
        float y,
        float alpha) noexcept {
        drawUiCircle(x - 0.013f * shortToX, y - 0.016f, 0.0072f, 0.96f, 0.98f, 1.0f, alpha, false);
        drawShortRect(x, y, 0.017f, 0.0036f, 0.96f, 0.98f, 1.0f, alpha);
        drawShortRect(x + 0.014f * shortToX, y + 0.012f, 0.004f, 0.012f, 0.96f, 0.98f, 1.0f, alpha);
        drawShortRect(x + 0.027f * shortToX, y + 0.022f, 0.015f, 0.0036f, 0.96f, 0.98f, 1.0f, alpha);
        drawShortRect(x - 0.016f * shortToX, y + 0.014f, 0.0035f, 0.012f, 0.96f, 0.98f, 1.0f, alpha * 0.85f);
    };

    // Android touch coordinates are top-origin while this renderer's UI
    // layout helpers are bottom-origin. Keep the input/HUD contract explicitly
    // top-origin for mobile controls and convert only at the renderer boundary.
    const auto mobileTopYToUiY = [](
        float topOriginY) noexcept {
        return 1.0f -
            std::clamp(
                topOriginY,
                0.0f,
                1.0f);
    };

    const float moveAnchorX =
        hud.moveActive
        ? std::clamp(
              hud.moveAnchorX,
              0.08f,
              0.42f)
        : 0.17f;

    const float moveAnchorTopY =
        hud.moveActive
        ? std::clamp(
              hud.moveAnchorY,
              0.55f,
              0.92f)
        : 0.74f;

    const float moveAnchorY =
        mobileTopYToUiY(
            moveAnchorTopY);

    // Tactical joystick pad: opaque enough to acquire instantly while still
    // leaving the world readable under the thumb.
    drawUiCircle(
        moveAnchorX,
        moveAnchorY,
        0.095f,
        0.025f,
        0.028f,
        0.030f,
        hud.moveActive ? 0.62f : 0.44f,
        false);
    drawUiCircle(
        moveAnchorX,
        moveAnchorY,
        0.095f,
        0.88f,
        0.96f,
        0.18f,
        hud.moveActive ? 0.90f : 0.46f,
        true,
        0.060f);

    const float knobTravel = 0.0684f;
    drawUiCircle(
        moveAnchorX +
            std::clamp(hud.moveX, -1.0f, 1.0f) *
            knobTravel * shortToX,
        moveAnchorY +
            std::clamp(hud.moveY, -1.0f, 1.0f) *
            knobTravel,
        0.031f,
        0.90f,
        0.94f,
        0.98f,
        hud.moveActive ? 0.72f : 0.30f,
        false);

    // Proven NZ:P Android control layout, reused as XZIEL's mobile baseline.
    constexpr float fireTopY = 0.585f;
    constexpr float aimTopY = 0.575f;
    constexpr float reloadTopY = 0.785f;
    constexpr float interactTopY = 0.675f;
    constexpr float jumpTopY = 0.790f;
    constexpr float stanceTopY = 0.800f;

    const float fireY = mobileTopYToUiY(fireTopY);
    const float aimY = mobileTopYToUiY(aimTopY);
    const float reloadY = mobileTopYToUiY(reloadTopY);
    const float interactY = mobileTopYToUiY(interactTopY);
    const float jumpY = mobileTopYToUiY(jumpTopY);
    const float stanceY = mobileTopYToUiY(stanceTopY);

    // FIRE: bullet silhouette, not an unlabeled neon ring.
    drawActionBackplate(0.885f, fireY, 0.073f, hud.fire);
    drawBulletIcon(0.885f, fireY, hud.fire ? 1.0f : 0.78f);

    // ADS: proper reticle.
    drawActionBackplate(0.695f, aimY, 0.047f, hud.aim);
    drawCrosshairIcon(0.695f, aimY, hud.aim ? 1.0f : 0.78f);

    // RELOAD: circular-arrow glyph.
    drawActionBackplate(0.805f, reloadY, 0.044f, hud.reload);
    drawReloadIcon(0.805f, reloadY, hud.reload ? 1.0f : 0.76f);

    if (hud.interactAvailable) {
        const float interactProgress =
            std::clamp(hud.interactProgress, 0.0f, 1.0f);
        const float denied =
            std::clamp(hud.interactionDeniedAlpha, 0.0f, 1.0f);
        const bool affordable = hud.interactionAffordable;

        const float interactR =
            denied > 0.001f || !affordable ? 0.98f : 0.78f;
        const float interactG =
            denied > 0.001f || !affordable ? 0.16f : 0.92f;
        const float interactB =
            denied > 0.001f || !affordable ? 0.16f : 1.0f;

        drawUiCircle(
            0.605f,
            interactY,
            0.050f,
            0.015f,
            0.020f,
            0.028f,
            0.32f,
            false);
        drawUiCircle(
            0.65f,
            interactY,
            0.050f,
            interactR,
            interactG,
            interactB,
            hud.interactHeld ? 0.82f : 0.46f,
            true,
            0.07f);
        drawShortRect(0.65f, interactY, 0.004f, 0.020f, interactR, interactG, interactB, 0.90f);
        drawShortRect(0.65f, interactY, 0.020f, 0.004f, interactR, interactG, interactB, 0.90f);

        if (interactProgress > 0.01f) {
            drawUiCircle(
                0.65f,
                interactY,
                0.038f + interactProgress * 0.008f,
                interactR,
                interactG,
                interactB,
                0.20f + interactProgress * 0.44f,
                true,
                0.045f);
        }

        if (hud.interactionCost > 0U) {
            std::array<int, 5> costDigits{};
            std::uint32_t costValue =
                std::min<std::uint32_t>(hud.interactionCost, 99999U);

            for (std::size_t reverseIndex = 0;
                 reverseIndex < costDigits.size();
                 ++reverseIndex) {
                const std::size_t index =
                    costDigits.size() - 1U - reverseIndex;
                costDigits[index] =
                    static_cast<int>(costValue % 10U);
                costValue /= 10U;
            }

            std::size_t firstCostDigit =
                costDigits.size() - 1U;
            for (std::size_t i = 0;
                 i + 1U < costDigits.size();
                 ++i) {
                if (costDigits[i] != 0) {
                    firstCostDigit = i;
                    break;
                }
            }

            float costX =
                0.65f -
                static_cast<float>(
                    costDigits.size() -
                    firstCostDigit) *
                    0.010f;

            const float costY =
                mobileTopYToUiY(
                    0.655f);

            for (std::size_t i = firstCostDigit;
                 i < costDigits.size();
                 ++i) {
                drawSevenSegmentDigit(
                    costDigits[i],
                    costX,
                    costY,
                    0.72f,
                    affordable
                        ? 0.78f
                        : 0.50f + denied * 0.40f);
                costX += 0.017f;
            }
        }
    }

    // JUMP/MANTLE and contextual STANCE get readable human silhouettes.
    drawActionBackplate(0.695f, jumpY, 0.044f, hud.jump);
    drawJumpIcon(0.695f, jumpY, hud.jump ? 1.0f : 0.80f);

    drawActionBackplate(0.915f, stanceY, 0.044f, hud.stance);
    drawCrouchIcon(0.915f, stanceY, hud.stance ? 1.0f : 0.80f);

    const float roundProgress =
        std::clamp(
            scene.roundProgress,
            0.0f,
            1.0f);

    constexpr float roundCenterX = 0.5f;
    constexpr float roundCenterY = 0.055f;
    constexpr float roundHalfWidth = 0.13f;
    constexpr float roundHalfHeight = 0.0035f;

    drawUiPrimitive(
        roundCenterX,
        roundCenterY,
        roundHalfWidth,
        roundHalfHeight,
        0.02f,
        0.025f,
        0.035f,
        0.62f,
        0.0f,
        0.10f);

    const float roundFill =
        std::max(
            roundHalfWidth *
                roundProgress,
            0.0005f);

    drawUiPrimitive(
        roundCenterX -
            roundHalfWidth +
            roundFill,
        roundCenterY,
        roundFill,
        roundHalfHeight * 0.70f,
        scene.interRound
            ? 0.72f
            : 0.62f,
        scene.interRound
            ? 0.16f
            : 0.06f,
        scene.interRound
            ? 0.96f
            : 0.78f,
        0.88f,
        0.0f,
        0.10f);

    const float magazineRatio =
        std::clamp(
            hud.weaponMagazineRatio,
            0.0f,
            1.0f);

    constexpr float ammoCenterX = 0.885f;
    constexpr float ammoCenterY = 0.935f;
    constexpr float ammoHalfWidth = 0.072f;
    constexpr float ammoHalfHeight = 0.0045f;

    drawUiPrimitive(
        ammoCenterX,
        ammoCenterY,
        ammoHalfWidth,
        ammoHalfHeight,
        0.02f,
        0.025f,
        0.035f,
        0.72f,
        0.0f,
        0.10f);

    const float ammoFillHalf =
        std::max(
            ammoHalfWidth *
                magazineRatio,
            0.0005f);

    const float ammoLeft =
        ammoCenterX -
        ammoHalfWidth;

    const float ammoFillCenter =
        ammoLeft +
        ammoFillHalf;

    const bool lowAmmo =
        magazineRatio <
        0.25f;

    drawUiPrimitive(
        ammoFillCenter,
        ammoCenterY,
        ammoFillHalf,
        ammoHalfHeight * 0.72f,
        lowAmmo ? 0.98f : 0.08f,
        lowAmmo ? 0.08f : 0.78f,
        lowAmmo ? 0.12f : 0.96f,
        0.92f,
        0.0f,
        0.10f);

    if (hud.weaponReloadAlpha > 0.001f) {
        const float reloadProgress =
            std::clamp(
                hud.weaponReloadAlpha,
                0.0f,
                1.0f);

        drawUiPrimitive(
            ammoLeft +
                ammoHalfWidth *
                reloadProgress,
            ammoCenterY - 0.014f,
            std::max(
                ammoHalfWidth *
                    reloadProgress,
                0.0005f),
            ammoHalfHeight * 0.48f,
            0.96f,
            0.62f,
            0.08f,
            0.78f,
            0.0f,
            0.10f);
    }

    const float healthRatio =
        std::clamp(
            hud.playerHealthRatio,
            0.0f,
            1.0f);

    constexpr float healthCenterX = 0.145f;
    constexpr float healthCenterY = 0.935f;
    constexpr float healthHalfWidth = 0.082f;
    constexpr float healthHalfHeight = 0.0050f;

    drawUiPrimitive(
        healthCenterX,
        healthCenterY,
        healthHalfWidth,
        healthHalfHeight,
        0.025f,
        0.020f,
        0.025f,
        0.76f,
        0.0f,
        0.10f);

    const float healthFillHalf =
        std::max(
            healthHalfWidth *
                healthRatio,
            0.0005f);

    drawUiPrimitive(
        healthCenterX -
            healthHalfWidth +
            healthFillHalf,
        healthCenterY,
        healthFillHalf,
        healthHalfHeight * 0.72f,
        0.96f -
            healthRatio * 0.70f,
        0.08f +
            healthRatio * 0.58f,
        0.12f,
        0.92f,
        0.0f,
        0.10f);

    const float damageFlash =
        std::clamp(
            hud.damageFlashAlpha,
            0.0f,
            1.0f);

    const float horrorVignette =
        std::clamp(
            hud.horrorVignette,
            0.0f,
            0.45f);

    const float edgeAlpha =
        std::clamp(
            damageFlash * 0.34f +
                horrorVignette * 0.45f,
            0.0f,
            0.52f);

    if (edgeAlpha > 0.001f) {
        drawUiPrimitive(
            0.5f,
            0.055f,
            0.5f,
            0.055f,
            0.34f,
            0.005f,
            0.012f,
            edgeAlpha,
            0.0f,
            0.10f);

        drawUiPrimitive(
            0.5f,
            0.945f,
            0.5f,
            0.055f,
            0.34f,
            0.005f,
            0.012f,
            edgeAlpha,
            0.0f,
            0.10f);

        drawUiPrimitive(
            0.035f,
            0.5f,
            0.035f,
            0.5f,
            0.34f,
            0.005f,
            0.012f,
            edgeAlpha,
            0.0f,
            0.10f);

        drawUiPrimitive(
            0.965f,
            0.5f,
            0.035f,
            0.5f,
            0.34f,
            0.005f,
            0.012f,
            edgeAlpha,
            0.0f,
            0.10f);
    }

    const float deathAlpha =
        std::clamp(
            hud.deathAlpha,
            0.0f,
            1.0f);

    if (deathAlpha > 0.001f) {
        drawUiPrimitive(
            0.5f,
            0.5f,
            0.5f,
            0.5f,
            0.035f,
            0.0f,
            0.006f,
            deathAlpha * 0.86f,
            0.0f,
            0.10f);
    }

    if (hud.restartVisible) {
        const float restartY =
            mobileTopYToUiY(
                0.62f);

        // Temporary death-screen preset: large, unmistakable restart button
        // centered under the reticle. Input uses the same normalized center
        // and radius, so the visual and touch target cannot drift apart.
        drawUiCircle(
            0.50f,
            restartY,
            0.13f,
            0.018f,
            0.022f,
            0.028f,
            0.88f,
            false);
        drawUiCircle(
            0.50f,
            restartY,
            0.13f,
            0.88f,
            0.96f,
            0.18f,
            0.96f,
            true,
            0.070f);

        drawUiCircle(
            0.50f,
            restartY,
            0.055f,
            0.98f,
            0.98f,
            0.98f,
            0.96f,
            true,
            0.11f);

        drawShortRect(
            0.50f +
                0.047f * shortToX,
            restartY -
                0.040f,
            0.020f,
            0.006f,
            0.018f,
            0.022f,
            0.028f,
            0.98f);
        drawShortRect(
            0.50f +
                0.050f * shortToX,
            restartY -
                0.040f,
            0.018f,
            0.0038f,
            0.98f,
            0.98f,
            0.98f,
            0.96f);
        drawShortRect(
            0.50f +
                0.058f * shortToX,
            restartY -
                0.028f,
            0.0040f,
            0.012f,
            0.98f,
            0.98f,
            0.98f,
            0.96f);
    }

    // Thin center reticle. Keeping this procedural avoids introducing font or
    // texture dependencies before the renderer has an asset streaming layer.
    const float hitMarker =
        std::clamp(
            hud.hitMarkerAlpha,
            0.0f,
            1.0f);

    const float criticalHit =
        std::clamp(
            hud.criticalHitAlpha,
            0.0f,
            1.0f);

    const float reticleR =
        std::min(
            1.0f,
            0.95f +
                criticalHit * 0.05f);

    const float reticleG =
        std::max(
            0.0f,
            0.96f -
                hitMarker * 0.78f -
                criticalHit * 0.14f);

    const float reticleB =
        std::max(
            0.0f,
            1.0f -
                hitMarker * 0.72f -
                criticalHit * 0.10f);

    const float reticleAlpha =
        0.72f +
        hitMarker * 0.24f;

    drawUiPrimitive(
        0.5f,
        0.5f,
        0.0011f,
        0.010f,
        reticleR,
        reticleG,
        reticleB,
        reticleAlpha,
        0.0f,
        0.10f);

    drawUiPrimitive(
        0.5f,
        0.5f,
        0.0060f,
        0.0016f,
        reticleR,
        reticleG,
        reticleB,
        reticleAlpha,
        0.0f,
        0.10f);

    if (hitMarker > 0.001f) {
        const float slashWidth =
            0.0012f +
            criticalHit * 0.0008f;

        const float slashHeight =
            0.013f +
            criticalHit * 0.009f;

        drawUiPrimitive(
            0.490f,
            0.490f,
            slashWidth,
            slashHeight,
            1.0f,
            0.10f,
            0.18f,
            hitMarker,
            0.0f,
            0.10f);

        drawUiPrimitive(
            0.510f,
            0.510f,
            slashWidth,
            slashHeight,
            1.0f,
            0.10f,
            0.18f,
            hitMarker,
            0.0f,
            0.10f);
    }

    if (hud.gyroAvailable) {
        drawUiCircle(
            0.965f,
            0.075f,
            0.010f,
            0.10f,
            0.82f,
            0.96f,
            0.58f,
            false);
    }

    flushUiPrimitiveBatch();

    if (performanceTelemetryFrame_ % 120U == 0U) {
        const std::uint32_t totalUiSubmissions =
            1U +
            uiBatchSubmissions +
            uiFallbackPrimitiveDraws +
            uiDigitDraws;

        __android_log_print(
            ANDROID_LOG_INFO,
            kTag,
            "XZIEL_UI_PRIMITIVE_BATCH logical_primitives=%u batch_submissions=%u fallback_primitives=%u digit_draws=%u digit_segments=%u total_submissions=%u",
            uiLogicalPrimitiveDraws,
            uiBatchSubmissions,
            uiFallbackPrimitiveDraws,
            uiDigitDraws,
            uiDigitSegments,
            totalUiSubmissions);
    }

    vkCmdEndRenderPass(command);

    if (gpuTimestampQueryPool_ != VK_NULL_HANDLE &&
        frameSlot < kFramesInFlight) {
        const std::uint32_t queryBase =
            frameSlot *
            kGpuTimestampQueriesPerFrame;

        vkCmdWriteTimestamp(
            command,
            VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
            gpuTimestampQueryPool_,
            queryBase + 3U);

        gpuTimestampValid_[frameSlot] = true;
    }

    if (!ok(
            vkEndCommandBuffer(
                command))) {
        logError("vkEndCommandBuffer failed");
        return false;
    }

    return true;
}

} // namespace xziel::android
