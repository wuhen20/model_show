"""
SM4 密码加密工具

使用方法:
1. 生成密钥（首次使用）:
   python encrypt_password.py --generate-key

2. 加密密码:
   python encrypt_password.py --encrypt "Faker@T169"

3. 加密用户名:
   python encrypt_password.py --encrypt "root"

输出会显示可直接复制到 .env 文件的配置格式。
"""

import argparse
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.core.crypto import sm4_encrypt, sm4_decrypt, generate_key, is_encrypted


def main():
    parser = argparse.ArgumentParser(description="SM4 密码加密工具")
    parser.add_argument("--generate-key", action="store_true", help="生成新的 SM4 密钥")
    parser.add_argument("--encrypt", metavar="TEXT", help="加密指定的文本")
    parser.add_argument("--decrypt", metavar="TEXT", help="解密指定的密文")
    parser.add_argument("--test", action="store_true", help="测试加解密功能")

    args = parser.parse_args()

    if args.generate_key:
        key_hex = generate_key()
        print("\n=== SM4 密钥已生成 ===")
        print(f"密钥（hex 格式）: {key_hex}")
        print("\n请将此密钥保存到以下位置之一:")
        print("  1. 环境变量: SM4_KEY=" + key_hex)
        print("  2. 文件 backend/sm4.key（内容为上述 hex 字符串）")
        print("\n⚠️  重要提示:")
        print("  - 密钥丢失将无法解密已加密的配置")
        print("  - 请妥善保管密钥，不要提交到代码仓库")
        print("  - 生产环境请使用强随机密钥")
        return

    if args.encrypt:
        text = args.encrypt
        encrypted = sm4_encrypt(text)
        decrypted = sm4_decrypt(encrypted)

        print("\n=== 加密结果 ===")
        print(f"原文: {text}")
        print(f"密文: {encrypted}")
        print(f"验证: {decrypted} ({'✓ 一致' if decrypted == text else '✗ 不一致'})")
        print("\n可直接复制到 .env 文件:")
        if text == "root" or len(text) < 10:  # 假设是用户名
            print(f"  DB_USER={encrypted}")
        else:
            print(f"  DB_PASSWORD={encrypted}")
        return

    if args.decrypt:
        text = args.decrypt
        if not is_encrypted(text):
            print("⚠️  输入的不是加密格式（应以 SM4: 开头）")
            return
        try:
            decrypted = sm4_decrypt(text)
            print("\n=== 解密结果 ===")
            print(f"密文: {text}")
            print(f"原文: {decrypted}")
        except Exception as e:
            print(f"解密失败: {e}")
        return

    if args.test:
        test_texts = ["root", "Faker@T169", "中文密码测试"]
        print("\n=== SM4_CBC 加解密测试 ===")
        for text in test_texts:
            encrypted = sm4_encrypt(text)
            decrypted = sm4_decrypt(encrypted)
            status = "✓" if decrypted == text else "✗"
            print(f"{status} 原文: {text}")
            print(f"   密文: {encrypted}")
            print(f"   解密: {decrypted}")
        return

    # 无参数时显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()