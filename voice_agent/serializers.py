"""Audio wire formats used by client transports."""

from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame
from pipecat.serializers.base_serializer import FrameSerializer


class BrowserPcmSerializer(FrameSerializer):
    """PCM16 mono: raw 16 kHz input and rate-tagged PCM16 output."""

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if not isinstance(data, bytes) or not data:
            return None
        return InputAudioRawFrame(audio=data, sample_rate=16_000, num_channels=1)

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if self.should_ignore_frame(frame) or not isinstance(frame, OutputAudioRawFrame):
            return None
        return int(frame.sample_rate).to_bytes(4, "little") + frame.audio
