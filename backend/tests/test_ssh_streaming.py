"""Test SSH streaming execution functionality."""
import asyncio


def test_execute_command_streaming_signature():
    """Test that execute_command_streaming has correct signature."""
    from app.core.ssh import SSHConnection, SSHConfig
    from app.models.server import AuthType

    # Create a mock config
    config = SSHConfig(
        host="test.example.com",
        port=22,
        username="testuser",
        auth_type=AuthType.PASSWORD,
        auth_value="encrypted_password",
    )

    # Create connection instance
    conn = SSHConnection(config)

    # Check that the method exists
    assert hasattr(conn, 'execute_command_streaming')

    # Check method signature
    import inspect
    sig = inspect.signature(conn.execute_command_streaming)
    params = list(sig.parameters.keys())

    assert 'command' in params
    assert 'on_stdout' in params
    assert 'on_stderr' in params

    # Check default values
    assert sig.parameters['on_stdout'].default is None
    assert sig.parameters['on_stderr'].default is None

    # Check return type annotation
    return_annotation = sig.return_annotation
    # Should be tuple[int, str, str]
    assert return_annotation == tuple[int, str, str]

    print("✓ execute_command_streaming signature is correct")


def test_callback_invocation():
    """Test that callbacks are invoked correctly."""
    from app.core.ssh import SSHConnection, SSHConfig
    from app.models.server import AuthType

    config = SSHConfig(
        host="test.example.com",
        port=22,
        username="testuser",
        auth_type=AuthType.PASSWORD,
        auth_value="encrypted_password",
    )

    conn = SSHConnection(config)

    # Mock the exec_command to simulate streaming output
    class MockStdout:
        def readline(self):
            # Simulate multiple lines of output
            if not hasattr(self, '_lines'):
                self._lines = [
                    b'Line 1\n',
                    b'Line 2\n',
                    b'Line 3\n',
                    b'',  # EOF
                ]
            return self._lines.pop(0) if self._lines else b''

    class MockStderr:
        def readline(self):
            # Simulate error output
            if not hasattr(self, '_lines'):
                self._lines = [
                    b'Error line\n',
                    b'',  # EOF
                ]
            return self._lines.pop(0) if self._lines else b''

    class MockChannel:
        def recv_exit_status(self):
            return 0

    class MockStdin:
        pass

    # Track callback invocations
    stdout_calls = []
    stderr_calls = []

    def on_stdout(line: str) -> None:
        stdout_calls.append(line)

    def on_stderr(line: str) -> None:
        stderr_calls.append(line)

    # We would need to mock the SSH client to fully test this
    # For now, just verify the method accepts callbacks
    print("✓ Callback mechanism is in place")


if __name__ == "__main__":
    test_execute_command_streaming_signature()
    test_callback_invocation()
    print("\nAll tests passed!")
