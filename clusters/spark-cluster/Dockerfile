FROM apache/hadoop:3.5.0

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/opt/hadoop/.local/bin:${PATH}"

RUN uv python install 3.11

