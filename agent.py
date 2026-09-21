from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import noise_cancellation, silero
from livekit.plugins import google 
from livekit.plugins.google.beta import realtime
from prompts import AGENT_INSTRUCTION , SESSION_INSTRUCTION

from tools import ALL_TOOLS

import os

from livekit.agents import function_tool, Agent, RunContext

load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            tools=ALL_TOOLS,
            llm = google.beta.realtime.RealtimeModel(
                model="models/gemini-2.5-flash-native-audio-latest",
                voice = "Aoede",
                temperature = 0.8
            )
        )
    @function_tool
    async def get_available_models(self, ctx: RunContext) -> str:
        """Fetch and return a list of available Google Gemini models."""
        models = await google.list_models()
        model_info = "\n".join(
            [f"Model name: {m.name}, Supported methods: {m.supported_generation_methods}" for m in models]
        )
        return f"Available Models:\n{model_info}"
    

async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()
    await session.start(
        room = ctx.room,
        agent = Assistant(),
        room_input_options = RoomInputOptions(
            video_enabled = False,
            noise_cancellation=noise_cancellation.BVC()
        )
    )

    await ctx.connect() 

    await session.generate_reply(
        instructions = SESSION_INSTRUCTION
    )

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint)) 

