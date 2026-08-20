"""Application-owned allowlist for controlled in-process tools."""

from trussium.tools.contracts import RegisteredTool


class ToolNotFoundError(ValueError):
    pass


class ToolRegistry:
    def __init__(self, tools: tuple[RegisteredTool, ...] = ()) -> None:
        registered_tools: dict[str, RegisteredTool] = {}
        for tool in tools:
            if not tool.name.strip():
                raise ValueError("Registered tool names must not be blank.")
            if tool.name in registered_tools:
                raise ValueError(f"Tool '{tool.name}' is registered more than once.")
            registered_tools[tool.name] = tool
        self._tools = registered_tools

    def require(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise ToolNotFoundError("The requested tool is not registered.") from error
