"""
============================================================
参数校验器 (Input Validator)
============================================================
层级: 输入规范层辅助模块
功能:
  1. 校验所有输入参数的类型、格式、范围
  2. 模糊描述 → 精确值转换
  3. 错误信息国际化
============================================================
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_params: dict = field(default_factory=dict)


class InputValidator:
    """
    参数校验器

    校验项:
      - 图片: 格式、大小、是否可读
      - 风格: 是否在支持列表中
      - 强度: mild / standard / extreme
      - 模型: midjourney / stable_diffusion / dall-e-3 / all
      - 画幅: X:Y 格式
      - 语言: english / chinese
    """

    # 校验规则
    VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
    VALID_IMAGE_MIMETYPES = {
        "image/png", "image/jpeg", "image/jpg",
        "image/webp", "image/gif", "image/bmp",
    }
    VALID_STYLES = {
        "dreamcore", "weirdcore", "liminal_space", "traumacore",
        "backrooms", "kidcore", "poolcore", "webcore",
        "hypnocore", "chinese_dreamcore",
    }
    VALID_INTENSITIES = {"mild", "standard", "extreme"}
    VALID_MODELS = {"midjourney", "stable_diffusion", "dall-e-3", "all"}
    VALID_LANGUAGES = {"english", "chinese"}

    ASPECT_RATIO_PATTERN = re.compile(r"^\d+:\d+$")
    MAX_IMAGE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
    MAX_RESOLUTION = 8192

    @classmethod
    def validate_image(cls, image_path: str) -> ValidationResult:
        """校验图片文件"""
        result = ValidationResult(is_valid=True)

        # 检查文件扩展名
        ext = None
        for valid_ext in cls.VALID_IMAGE_EXTENSIONS:
            if image_path.lower().endswith(valid_ext):
                ext = valid_ext
                break

        if not ext:
            result.is_valid = False
            result.errors.append(
                f"不支持的图片格式。支持: {', '.join(sorted(cls.VALID_IMAGE_EXTENSIONS))}"
            )
            return result

        # 检查文件是否存在
        import os
        if not os.path.exists(image_path):
            result.is_valid = False
            result.errors.append("图片文件不存在，请确认文件路径。")
            return result

        # 检查文件大小
        file_size = os.path.getsize(image_path)
        if file_size > cls.MAX_IMAGE_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            result.is_valid = False
            result.errors.append(
                f"图片过大（{size_mb:.1f}MB），最大支持 50MB。请压缩后重新上传。"
            )
            return result

        if file_size == 0:
            result.is_valid = False
            result.errors.append("图片文件为空。")
            return result

        result.normalized_params["image_path"] = image_path
        result.normalized_params["image_size_bytes"] = file_size
        return result

    @classmethod
    def validate_style(cls, style_input: str) -> ValidationResult:
        """校验风格参数"""
        result = ValidationResult(is_valid=True)

        # 先尝试精确匹配
        if style_input in cls.VALID_STYLES:
            result.normalized_params["style"] = style_input
            return result

        # 尝试通过风格匹配器解析
        from core.style_matcher import StyleMatcher
        match_result = StyleMatcher.resolve(style_input)

        if match_result["resolved"] and match_result["confidence"] >= 0.5:
            result.normalized_params["style"] = match_result["style_id"]
            result.normalized_params["style_confidence"] = match_result["confidence"]
            if match_result["confidence"] < 0.8:
                result.warnings.append(
                    f"风格「{style_input}」匹配到「{match_result['style_id']}」（置信度 {match_result['confidence']:.0%}）"
                )
            return result

        result.is_valid = False
        result.errors.append(
            f"未识别到风格「{style_input}」。支持: {', '.join(sorted(cls.VALID_STYLES))}"
        )
        return result

    @classmethod
    def validate_intensity(cls, intensity: str) -> ValidationResult:
        """校验并标准化强度参数"""
        result = ValidationResult(is_valid=True)

        intensity_lower = intensity.lower().strip()

        # 精确匹配
        if intensity_lower in cls.VALID_INTENSITIES:
            result.normalized_params["intensity"] = intensity_lower
            return result

        # 模糊匹配
        intensity_map = {
            "mild": ["轻", "淡", "柔和", "温和", "一点点", "轻微", "轻一点", "淡一点"],
            "standard": ["正常", "标准", "适中", "默认", "普通"],
            "extreme": ["强烈", "极致", "拉满", "重度", "极限", "猛", "重一点", "强一点"],
        }

        for target, keywords in intensity_map.items():
            if any(kw in intensity_lower for kw in keywords):
                result.normalized_params["intensity"] = target
                result.warnings.append(f"已将强度「{intensity}」标准化为「{target}」")
                return result

        # 默认值
        result.normalized_params["intensity"] = "standard"
        result.warnings.append(f"未识别强度「{intensity}」，使用默认值「standard」")
        return result

    @classmethod
    def validate_model(cls, model: str) -> ValidationResult:
        """校验目标模型"""
        result = ValidationResult(is_valid=True)
        model_lower = model.lower().strip()

        if model_lower in cls.VALID_MODELS:
            result.normalized_params["model"] = model_lower
            return result

        # 别名匹配
        aliases = {
            "midjourney": ["mj"],
            "stable_diffusion": ["sd", "stablediffusion"],
            "dall-e-3": ["dalle", "dall-e", "dalle3", "openai"],
        }
        for target, alias_list in aliases.items():
            if model_lower in alias_list or any(a in model_lower for a in alias_list):
                result.normalized_params["model"] = target
                return result

        # 默认
        result.normalized_params["model"] = "midjourney"
        result.warnings.append(f"未识别模型「{model}」，使用默认值「midjourney」")
        return result

    @classmethod
    def validate_aspect_ratio(cls, ratio: str) -> ValidationResult:
        """校验画面比例"""
        result = ValidationResult(is_valid=True)

        if not ratio:
            result.normalized_params["aspect_ratio"] = None  # 使用风格默认值
            return result

        if cls.ASPECT_RATIO_PATTERN.match(ratio):
            result.normalized_params["aspect_ratio"] = ratio
            return result

        result.is_valid = False
        result.errors.append(f"画面比例格式不正确: {ratio}。请使用 X:Y 格式，如 16:9、4:3。")
        return result

    @classmethod
    def validate_all(cls, **kwargs) -> ValidationResult:
        """
        综合校验所有参数

        Args:
            image_path: 图片路径
            style: 目标风格
            intensity: 风格强度
            model: 目标模型
            aspect_ratio: 画面比例
            language: 提示词语言

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)

        # 必填参数
        if "image_path" in kwargs and kwargs["image_path"]:
            img_result = cls.validate_image(kwargs["image_path"])
            result.errors.extend(img_result.errors)
            result.warnings.extend(img_result.warnings)
            result.normalized_params.update(img_result.normalized_params)
            if not img_result.is_valid:
                result.is_valid = False
        else:
            result.is_valid = False
            result.errors.append("缺少必填参数: image_path（图片路径）")

        if "style" in kwargs and kwargs["style"]:
            style_result = cls.validate_style(kwargs["style"])
            result.errors.extend(style_result.errors)
            result.warnings.extend(style_result.warnings)
            result.normalized_params.update(style_result.normalized_params)
            if not style_result.is_valid:
                result.is_valid = False
        else:
            result.is_valid = False
            result.errors.append("缺少必填参数: style（目标风格）")

        # 可选参数
        if "intensity" in kwargs and kwargs["intensity"]:
            int_result = cls.validate_intensity(kwargs["intensity"])
            result.warnings.extend(int_result.warnings)
            result.normalized_params.update(int_result.normalized_params)

        if "model" in kwargs and kwargs["model"]:
            model_result = cls.validate_model(kwargs["model"])
            result.warnings.extend(model_result.warnings)
            result.normalized_params.update(model_result.normalized_params)

        if "aspect_ratio" in kwargs and kwargs["aspect_ratio"]:
            ar_result = cls.validate_aspect_ratio(kwargs["aspect_ratio"])
            result.errors.extend(ar_result.errors)
            result.warnings.extend(ar_result.warnings)
            result.normalized_params.update(ar_result.normalized_params)
            if not ar_result.is_valid:
                result.is_valid = False

        return result
