"""
演示增强的部署脚本执行日志输出

这个脚本展示了如何使用 execute_command_streaming 方法
来获取实时的命令输出。
"""


async def demo_streaming_output():
    """演示流式输出的使用示例。"""
    import asyncio

    # 模拟部署日志记录器
    class MockDeploymentLogger:
        async def info(self, message: str) -> None:
            print(f"INFO  {message}")

        async def error(self, message: str) -> None:
            print(f"ERROR {message}")

        async def warning(self, message: str) -> None:
            print(f"WARN  {message}")

    logger = MockDeploymentLogger()

    print("=" * 60)
    print("演示：部署脚本执行的增强日志输出")
    print("=" * 60)

    # 模拟脚本执行的日志输出
    await logger.info("准备执行部署脚本: restart.sh")
    await logger.info("脚本路径: /opt/app/scripts/restart.sh")
    await logger.info("工作目录: /opt/app")
    await logger.info("执行命令: cd /opt/app && bash /opt/app/scripts/restart.sh")

    # 模拟实时输出
    print("\n--- 实时输出开始 ---")

    # 模拟成功的脚本执行
    outputs = [
        ("[stdout] Stopping application...", "info"),
        ("[stdout] Application stopped", "info"),
        ("[stdout] Starting application...", "info"),
        ("[stdout] Application started successfully", "info"),
    ]

    for output, level in outputs:
        if level == "info":
            await logger.info(output)
        await asyncio.sleep(0.1)  # 模拟延迟

    print("--- 实时输出结束 ---\n")
    await logger.info("脚本执行完成，退出码: 0")
    await logger.info("部署脚本执行成功")

    print("\n" + "=" * 60)
    print("演示：解压过程的增强日志输出")
    print("=" * 60)

    await logger.info("开始解压到 /opt/app")
    await logger.info("解压命令: mkdir -p /opt/app && unzip -o /tmp/artifact.zip -d /opt/app && rm /tmp/artifact.zip")

    print("\n--- 实时输出开始 ---")

    # 模拟解压输出
    unzip_outputs = [
        ("[stdout] Archive: /tmp/artifact.zip", "info"),
        ("[stdout] inflating: /opt/app/app.py", "info"),
        ("[stdout] inflating: /opt/app/requirements.txt", "info"),
        ("[stdout] inflating: /opt/app/config.yaml", "info"),
    ]

    for output, level in unzip_outputs:
        if level == "info":
            await logger.info(output)
        await asyncio.sleep(0.1)

    print("--- 实时输出结束 ---\n")
    await logger.info("解压完成，退出码: 0")

    print("\n" + "=" * 60)
    print("演示：失败的脚本执行")
    print("=" * 60)

    await logger.info("准备执行部署脚本: restart.sh")
    await logger.info("脚本路径: /opt/app/scripts/restart.sh")
    await logger.info("工作目录: /opt/app")
    await logger.info("执行命令: cd /opt/app && bash /opt/app/scripts/restart.sh")

    print("\n--- 实时输出开始 ---")

    # 模拟失败的脚本执行
    error_outputs = [
        ("[stdout] Stopping application...", "info"),
        ("[stderr] Error: Application not running", "error"),
        ("[stderr] Failed to stop application", "error"),
    ]

    for output, level in error_outputs:
        if level == "info":
            await logger.info(output)
        elif level == "error":
            await logger.error(output)
        await asyncio.sleep(0.1)

    print("--- 实时输出结束 ---\n")
    await logger.error("脚本执行完成，退出码: 1")
    await logger.error("部署脚本执行失败")

    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


async def demo_api_usage():
    """演示 API 的使用方法。"""
    print("\n" + "=" * 60)
    print("API 使用示例")
    print("=" * 60)

    code_example = '''
# 在 deploy_service.py 中的使用示例

async def _deploy_to_server(self, server: Server, artifact_path: Path):
    conn = create_ssh_connection(server)

    with conn:
        # 使用流式输出执行命令
        exit_code, stdout, stderr = conn.execute_command_streaming(
            command="cd /opt/app && bash restart.sh",
            on_stdout=lambda line: asyncio.create_task(
                self.logger.info(f"[stdout] {line}")
            ),
            on_stderr=lambda line: asyncio.create_task(
                self.logger.info(f"[stderr] {line}")
            ),
        )

        # 根据退出码记录结果
        if exit_code != 0:
            await self.logger.error(f"脚本执行完成，退出码: {exit_code}")
            await self.logger.error("部署脚本执行失败")
        else:
            await self.logger.info(f"脚本执行完成，退出码: {exit_code}")
            await self.logger.info("部署脚本执行成功")
'''

    print(code_example)


if __name__ == "__main__":
    import asyncio

    # 运行演示
    asyncio.run(demo_streaming_output())
    asyncio.run(demo_api_usage())
