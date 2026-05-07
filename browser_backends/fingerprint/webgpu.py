from __future__ import annotations

import re
from typing import Any

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_webgpu_patch(config: FingerprintConfig) -> str:
    return _render_js_template("webgpu.js", _webgpu_profile(config))


def _webgpu_profile(config: FingerprintConfig) -> dict[str, Any]:
    renderer = config.webgl_renderer or "ANGLE"
    vendor = config.webgl_vendor or "Google Inc."
    vendor_key = _webgpu_vendor_key(vendor, renderer)
    return {
        "adapterInfo": {
            "vendor": vendor_key,
            "architecture": _webgpu_architecture(renderer),
            "device": _webgpu_device(renderer),
            "description": renderer,
        },
        "adapterName": renderer,
        "canvasFormat": "bgra8unorm",
        "features": _webgpu_features(vendor_key),
        "limits": _webgpu_limits(vendor_key),
    }


def _webgpu_vendor_key(vendor: str, renderer: str) -> str:
    source = f"{vendor} {renderer}".lower()
    if "nvidia" in source:
        return "nvidia"
    if "amd" in source or "radeon" in source:
        return "amd"
    if "apple" in source or "metal" in source:
        return "apple"
    if "intel" in source:
        return "intel"
    return "google"


def _webgpu_architecture(renderer: str) -> str:
    source = renderer.lower()
    if "apple m" in source:
        return "apple-silicon"
    if "rtx" in source:
        return "nvidia-rtx"
    if "gtx" in source:
        return "nvidia-gtx"
    if "radeon" in source:
        return "amd-radeon"
    if "iris" in source or "uhd" in source:
        return "intel-gen"
    return ""


def _webgpu_device(renderer: str) -> str:
    match = re.search(
        r"(Apple M[0-9][^,\)]*|NVIDIA [^,\)]*|AMD Radeon [^,\)]*|Intel\(R\) [^,\)]*|Intel [^,\)]*)",
        renderer,
    )
    if not match:
        return ""
    return " ".join(match.group(1).split())


def _webgpu_features(vendor_key: str) -> list[str]:
    features = ["depth-clip-control", "texture-compression-bc"]
    if vendor_key in {"nvidia", "amd", "intel"}:
        features.extend(["timestamp-query", "indirect-first-instance"])
    if vendor_key == "apple":
        features.append("rg11b10ufloat-renderable")
    return features


def _webgpu_limits(vendor_key: str) -> dict[str, int]:
    high_power = vendor_key in {"nvidia", "amd", "apple"}
    max_texture_size = 16_384 if high_power else 8_192
    max_buffer_size = 2_147_483_648 if high_power else 1_073_741_824
    return {
        "maxTextureDimension1D": max_texture_size,
        "maxTextureDimension2D": max_texture_size,
        "maxTextureDimension3D": 2_048,
        "maxTextureArrayLayers": 2_048,
        "maxBindGroups": 4,
        "maxBindGroupsPlusVertexBuffers": 24,
        "maxBindingsPerBindGroup": 1_000,
        "maxDynamicUniformBuffersPerPipelineLayout": 8,
        "maxDynamicStorageBuffersPerPipelineLayout": 4,
        "maxSampledTexturesPerShaderStage": 16,
        "maxSamplersPerShaderStage": 16,
        "maxStorageBuffersPerShaderStage": 8,
        "maxStorageTexturesPerShaderStage": 4,
        "maxUniformBuffersPerShaderStage": 12,
        "maxUniformBufferBindingSize": 65_536,
        "maxStorageBufferBindingSize": max_buffer_size,
        "minUniformBufferOffsetAlignment": 256,
        "minStorageBufferOffsetAlignment": 256,
        "maxVertexBuffers": 8,
        "maxBufferSize": max_buffer_size,
        "maxVertexAttributes": 16,
        "maxVertexBufferArrayStride": 2_048,
        "maxInterStageShaderComponents": 60,
        "maxInterStageShaderVariables": 16,
        "maxColorAttachments": 8,
        "maxColorAttachmentBytesPerSample": 32,
        "maxComputeWorkgroupStorageSize": 32_768,
        "maxComputeInvocationsPerWorkgroup": 256,
        "maxComputeWorkgroupSizeX": 256,
        "maxComputeWorkgroupSizeY": 256,
        "maxComputeWorkgroupSizeZ": 64,
        "maxComputeWorkgroupsPerDimension": 65_535,
    }
