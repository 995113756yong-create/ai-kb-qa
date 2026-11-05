import io

t = io.open("frontend/lib/types.ts", encoding="utf-8").read()
i = t.find("AgentEvent")
print("=== types.ts AgentEvent ===")
print(t[i - 200 : i + 1400])
