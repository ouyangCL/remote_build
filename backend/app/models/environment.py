"""Environment type enumeration."""
import enum


class EnvironmentType(str, enum.Enum):
    """环境类型枚举"""
    DEVELOPMENT = "development"  # 开发/测试环境
    PRODUCTION = "production"    # 生产环境
