# Reproduction and revision

There are three different promises. Record which one was tested.

1. **Frozen-source replay:** identical selected inputs, code and settings regenerate the same finishing output. The reference SVG demo verifies this with SHA-256.
2. **Controlled revision:** one requested change, such as background colour, is produced while product identity and all locked decisions remain stable. Measure elapsed time, cost and reviewer acceptance.
3. **Fresh generation:** a remote or local generative model produces a new result. A seed is useful metadata but does not guarantee identical bytes across model or service updates.

The demo freezes its JSON input and compares the output hash on replay. Receipt timestamps and run paths deliberately differ. This establishes only the synthetic renderer's determinism. It does not benchmark GPU rendering or cloud generations.

For a DCC integration, record the software build, renderer, device, driver, camera, geometry/texture hashes, colour configuration, samples and denoising. Package external textures, fonts and caches as permitted. Reopen on a clean machine, resolve paths and render one representative frame before claiming portability.

For compositing, freeze image sources, masks, typography and encode settings. Keep an uncompressed comparison where possible. File-level equality, decoded-frame equality and visual equivalence are different measurements. State the one actually checked.

Restore a backup to a new location and verify all manifest hashes before testing replay. Do not overwrite the original. Upgrade dependencies in a separate workspace copy, rerun the acceptance sample and retain rollback instructions.
