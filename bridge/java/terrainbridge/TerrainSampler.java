package terrainbridge;

import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.List;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.resources.MultiPackResourceManager;
import net.minecraft.SharedConstants;
import net.minecraft.core.registries.Registries;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.RegistryAccess;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.server.Bootstrap;
import net.minecraft.server.packs.repository.ServerPacksSource;
import net.minecraft.tags.TagLoader;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.biome.FixedBiomeSource;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.RandomState;

/** Samples actual vanilla 26.3 base terrain. No game classes or assets are redistributed. */
public final class TerrainSampler {
    public static void main(String[] args) throws Exception {
        if (args.length != 6) throw new IllegalArgumentException("seed centerX centerZ span grid output.json");
        long seed = Long.parseLong(args[0]);
        int centerX = Integer.parseInt(args[1]), centerZ = Integer.parseInt(args[2]);
        int span = Integer.parseInt(args[3]), grid = Integer.parseInt(args[4]);
        if (span < 32 || span > 2048 || grid < 9 || grid > 129 || span % (grid - 1) != 0)
            throw new IllegalArgumentException("Invalid sample dimensions");
        if (Math.abs((long)centerX) + span > 30000000 || Math.abs((long)centerZ) + span > 30000000)
            throw new IllegalArgumentException("Sample is outside Minecraft's world border");
        Path output = Path.of(args[5]);
        if (Files.exists(output)) throw new IllegalArgumentException("Refusing to replace an existing sample");
        SharedConstants.tryDetectVersion();
        if (!SharedConstants.getCurrentVersion().id().equals("26.3"))
            throw new IllegalStateException("The sampler requires Minecraft 26.3");
        Bootstrap.bootStrap();
        // 26.3 heightmap predicates use data-driven block tags. Bootstrap alone leaves them empty.
        var resources = new MultiPackResourceManager(PackType.SERVER_DATA, List.of(ServerPacksSource.createVanillaPackSource().fullResources()));
        var builtin = RegistryAccess.fromRegistryOfRegistries(BuiltInRegistries.REGISTRY);
        for (var pending : TagLoader.loadTagsForExistingRegistries(resources, builtin)) pending.apply();
        var registries = VanillaRegistries.createWorldLookup();
        var settings = registries.lookupOrThrow(Registries.NOISE_SETTINGS).getOrThrow(NoiseGeneratorSettings.OVERWORLD);
        var biome = registries.lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.FOREST);
        var generator = new NoiseBasedChunkGenerator(new FixedBiomeSource(biome), settings);
        var random = RandomState.create(registries.lookupOrThrow(Registries.NOISE), seed, settings.value());
        var height = LevelHeightAccessor.create(generator.getMinY(), generator.getGenDepth());
        int[][] heights = new int[grid][grid];
        int step = span / (grid - 1), originX = centerX - span / 2, originZ = centerZ - span / 2;
        int minimum = Integer.MAX_VALUE, maximum = Integer.MIN_VALUE;
        for (int z = 0; z < grid; z++) {
            for (int x = 0; x < grid; x++) {
                int value = generator.getBaseHeight(originX + x * step, originZ + z * step,
                    Heightmap.Types.OCEAN_FLOOR_WG, height, random);
                heights[z][x] = value;
                minimum = Math.min(minimum, value);
                maximum = Math.max(maximum, value);
            }
            System.out.println("BC_PROGRESS " + (z + 1) + " " + grid);
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("format", 1);
        result.put("minecraft", "26.3");
        result.put("engine", "NoiseBasedChunkGenerator.getBaseHeight(OCEAN_FLOOR_WG)");
        result.put("seed", Long.toString(seed));
        result.put("center_x", centerX);
        result.put("center_z", centerZ);
        result.put("span", span);
        result.put("grid", grid);
        result.put("step", step);
        result.put("origin_x", originX);
        result.put("origin_z", originZ);
        result.put("sea_level", generator.getSeaLevel());
        result.put("min_height", minimum);
        result.put("max_height", maximum);
        result.put("heights", heights);
        Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output, new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("BC_COMPLETE " + output.toAbsolutePath());
    }
}
