#!/bin/sh
ollama serve &
sleep 5
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
wait
