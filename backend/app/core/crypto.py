"""
SM4_CBC 加解密工具模块

加密配置格式: SM4:<base64(IV + ciphertext)>
- IV: 16字节随机生成
- 密钥: 16字节，从环境变量 SM4_KEY 或文件 sm4.key 读取
- 填充: PKCS7

使用方法:
1. 设置 SM4_KEY 环境变量（16字节密钥的 hex 或 base64 编码）
   或将密钥写入 backend/sm4.key 文件（纯文本，16字节）

2. 运行 encrypt_password.py 生成加密密文

3. 在 .env 中配置: DB_PASSWORD=SM4:加密密文

4. config.py 自动解密带 SM4: 前缀的配置值
"""

import os
import base64
from pathlib import Path

# gmssl 提供 SM4 实现
try:
    from gmssl import sm4
except ImportError:
    raise ImportError(
        "请安装 gmssl 库: pip install gmssl\n"
        "或使用 pip install gmssl-python（较新版本）"
    )


# ==================== 密钥管理 ====================

_KEY_CACHE: bytes | None = None


def _load_env_file() -> dict:
    """手动加载 .env 文件（因为 Settings 此时还未初始化）"""
    env_file = Path(__file__).parent.parent.parent / ".env"  # backend/.env
    if not env_file.is_file():
        return {}
    result = {}
    # 尝试 UTF-8 和 GBK 编码
    for encoding in ("utf-8", "gbk"):
        try:
            content = env_file.read_text(encoding=encoding)
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    result[key.strip()] = value.strip()
            return result
        except UnicodeDecodeError:
            continue
    return result


def _get_sm4_key() -> bytes:
    """获取 SM4 密钥（16字节）

    优先级:
    1. 环境变量 SM4_KEY（支持 hex 或 base64 编码）
    2. .env 文件中的 SM4_KEY
    3. 文件 backend/sm4.key（纯文本，16字节）
    4. 报错提示用户设置
    """
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE

    def _try_decode_key(key_str: str) -> bytes | None:
        """尝试多种格式解码密钥"""
        if not key_str:
            return None
        # hex 格式（32字符 = 16字节）
        if len(key_str) == 32:
            try:
                return bytes.fromhex(key_str)
            except ValueError:
                pass
        # base64 格式
        try:
            decoded = base64.b64decode(key_str)
            if len(decoded) == 16:
                return decoded
        except Exception:
            pass
        # 原始16字节字符串
        if len(key_str) == 16:
            return key_str.encode("utf-8")
        return None

    # 1. 从环境变量读取
    env_key = os.environ.get("SM4_KEY", "").strip()
    _KEY_CACHE = _try_decode_key(env_key)
    if _KEY_CACHE is not None:
        return _KEY_CACHE

    # 2. 从 .env 文件读取
    env_dict = _load_env_file()
    env_key = env_dict.get("SM4_KEY", "").strip()
    _KEY_CACHE = _try_decode_key(env_key)
    if _KEY_CACHE is not None:
        return _KEY_CACHE

    # 3. 从文件读取
    key_file = Path(__file__).parent.parent.parent / "sm4.key"  # backend/sm4.key
    if key_file.is_file():
        try:
            key_text = key_file.read_text(encoding="utf-8").strip()
            _KEY_CACHE = _try_decode_key(key_text)
            if _KEY_CACHE is not None:
                return _KEY_CACHE
        except Exception:
            pass

    # 4. 未找到密钥
    raise RuntimeError(
        "SM4 密钥未配置。请设置:\n"
        "  - 环境变量 SM4_KEY\n"
        "  - 或 .env 文件中的 SM4_KEY\n"
        "  - 或文件 backend/sm4.key\n"
        "密钥格式: 32字符 hex（推荐）或 base64 编码\n"
        "示例密钥（请勿在生产环境使用）: 0123456789abcdef0123456789abcdef"
    )


# ==================== 加解密核心 ====================

SM4_PREFIX = "SM4:"
SM4_KEY_LENGTH = 16  # SM4 密钥长度（字节）
SM4_IV_LENGTH = 16   # CBC 模式 IV 长度（字节）
SM4_BLOCK_SIZE = 16  # SM4 分组大小（字节）


def _pkcs7_pad(data: bytes) -> bytes:
    """PKCS7 填充"""
    pad_len = SM4_BLOCK_SIZE - (len(data) % SM4_BLOCK_SIZE)
    return data + bytes([pad_len] * pad_len)


def _pkcs7_unpad(data: bytes) -> bytes:
    """去除 PKCS7 填充"""
    if not data:
        return data
    pad_len = data[-1]
    if pad_len < 1 or pad_len > SM4_BLOCK_SIZE:
        raise ValueError("无效的 PKCS7 填充")
    # 验证填充字节
    for i in range(-pad_len, 0):
        if data[i] != pad_len:
            raise ValueError("无效的 PKCS7 填充")
    return data[:-pad_len]


def sm4_encrypt(plaintext: str | bytes) -> str:
    """SM4_CBC 加密，返回带前缀的密文字符串

    Args:
        plaintext: 待加密的字符串或字节

    Returns:
        格式: SM4:<base64(IV + ciphertext)>
    """
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")

    key = _get_sm4_key()
    iv = os.urandom(SM4_IV_LENGTH)  # 随机 IV

    # PKCS7 填充
    padded = _pkcs7_pad(plaintext)

    # SM4_CBC 加密
    cipher = sm4.CryptSM4()
    cipher.set_key(key, sm4.SM4_ENCRYPT)
    ciphertext = cipher.crypt_cbc(iv, padded)

    # 组合 IV + 密文，base64 编码
    combined = iv + ciphertext
    encoded = base64.b64encode(combined).decode("utf-8")

    return f"{SM4_PREFIX}{encoded}"


def sm4_decrypt(enc_string: str) -> str:
    """SM4_CBC 解密

    Args:
        enc_string: 带前缀的密文字符串，格式 SM4:<base64(IV + ciphertext)>

    Returns:
        解密后的原始字符串
    """
    if not enc_string.startswith(SM4_PREFIX):
        # 不是加密格式，直接返回原值
        return enc_string

    # 提取 base64 部分
    encoded = enc_string[len(SM4_PREFIX):]

    try:
        combined = base64.b64decode(encoded)
    except Exception as e:
        raise ValueError(f"无效的 base64 编码: {e}")

    if len(combined) < SM4_IV_LENGTH + SM4_BLOCK_SIZE:
        raise ValueError("密文长度不足")

    # 分离 IV 和密文
    iv = combined[:SM4_IV_LENGTH]
    ciphertext = combined[SM4_IV_LENGTH:]

    # SM4_CBC 解密
    key = _get_sm4_key()
    cipher = sm4.CryptSM4()
    cipher.set_key(key, sm4.SM4_DECRYPT)
    decrypted = cipher.crypt_cbc(iv, ciphertext)

    # 去除 PKCS7 填充
    unpadded = _pkcs7_unpad(decrypted)

    return unpadded.decode("utf-8")


def is_encrypted(value: str) -> bool:
    """判断配置值是否为加密格式"""
    return isinstance(value, str) and value.startswith(SM4_PREFIX)


# ==================== 密钥生成工具 ====================

def generate_key() -> str:
    """生成随机 SM4 密钥（32字符 hex 格式）"""
    key_bytes = os.urandom(SM4_KEY_LENGTH)
    return key_bytes.hex()


if __name__ == "__main__":
    # 测试加解密
    print("=== SM4_CBC 加解密测试 ===")
    print(f"密钥（hex）: {_get_sm4_key().hex()}")

    test_text = "Faker@T169"
    encrypted = sm4_encrypt(test_text)
    decrypted = sm4_decrypt(encrypted)

    print(f"原文: {test_text}")
    print(f"密文: {encrypted}")
    print(f"解密: {decrypted}")
    print(f"一致: {test_text == decrypted}")