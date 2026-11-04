# ComfyUI models

Every model file a saved workflow in `workflows/` uses, with its licence. Decision D-M3 allows only open licences
(Apache-2.0, MIT and similar; SDXL's CreativeML OpenRAIL++-M counts as allowed). `scripts/stacklib/media.py` holds the
same list (`MODELS`) and refuses to download anything else; `tests/test_media.py` checks that the two agree and that
every file a workflow names is listed.

`uv run scripts/stack.py media install` (or the installer's media option) downloads them into
`<media.root>\comfyui\models\<folder>`.

| File | Folder | Source | Licence | Size | Workflow |
|---|---|---|---|---|---|
| `z_image_turbo_int8_convrot.safetensors` | `diffusion_models` | [Comfy-Org/z_image_turbo](https://huggingface.co/Comfy-Org/z_image_turbo), repack of [Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) | Apache-2.0 | 6.2 GB | `z_image_turbo` |
| `qwen_3_4b_fp8_mixed.safetensors` | `text_encoders` | same repository (Qwen3-4B text encoder) | Apache-2.0 | 5.6 GB | `z_image_turbo` |
| `ae.safetensors` | `vae` | same repository (autoencoder) | Apache-2.0 | 0.3 GB | `z_image_turbo` |

Licences read from the Hugging Face model cards on 2026-11-04. Why the int8 build: the bf16 weights are 12.3 GB and
would not fit the 12 GB card next to the chat model; int8 runs natively on RTX 30xx (Ampere). The nvfp4 build needs an
RTX 50xx.

## Custom nodes

None. The image workflow uses only nodes built into ComfyUI (0.44.0, commit `56f179f6`).
