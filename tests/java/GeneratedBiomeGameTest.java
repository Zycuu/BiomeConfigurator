package validation;

import net.fabricmc.fabric.api.gametest.v1.GameTest;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.resources.Identifier;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.levelgen.Heightmap;

/** Integration smoke test against a disposable Far Dark project copy. */
public final class GeneratedBiomeGameTest {
    @GameTest(maxTicks = 200)
    public void biomeAndTreesLoad(GameTestHelper helper) {
        var level = helper.getLevel();
        var access = level.registryAccess();
        Identifier biomeId = Identifier.parse("far_dark:gloam_woods");
        if (!access.lookupOrThrow(Registries.BIOME).containsKey(biomeId)) {
            helper.fail("Generated biome is missing"); return;
        }
        Block dirt = BuiltInRegistries.BLOCK.getValue(Identifier.parse("far_dark:ash_dirt"));
        BlockPos origin = helper.absolutePos(new BlockPos(5, 3, 5));
        for (int x = -3; x <= 3; x++) for (int z = -3; z <= 3; z++) {
            level.setBlockAndUpdate(origin.offset(x, 0, z), dirt.defaultBlockState());
            for (int y = 1; y <= 12; y++)
                level.setBlockAndUpdate(origin.offset(x, y, z), net.minecraft.world.level.block.Blocks.AIR.defaultBlockState());
        }
        var tree = access.lookupOrThrow(Registries.FEATURE).getValue(Identifier.parse("far_dark:bc/gloam_woods/tree1"));
        if (tree == null || !tree.place(level, level.getChunkSource().getGenerator(), RandomSource.create(416), origin.above())) {
            helper.fail("Custom tree failed to generate on Ash Dirt"); return;
        }
        if (!BuiltInRegistries.BLOCK.getKey(level.getBlockState(origin.above()).getBlock()).equals(Identifier.parse("far_dark:gloom_oak_log"))) {
            helper.fail("Custom tree did not use Gloom Oak logs"); return;
        }
        if (!access.lookupOrThrow(Registries.MATERIAL_RULE).containsKey(Identifier.parse("far_dark:bc_surface"))) {
            helper.fail("Custom terrain material rules did not load"); return;
        }
        if (!access.lookupOrThrow(Registries.NOISE_SETTINGS).containsKey(Identifier.parse("far_dark:bc/gloam_woods_preview"))) {
            helper.fail("Preview noise settings did not load"); return;
        }
        helper.succeed();
    }
}
