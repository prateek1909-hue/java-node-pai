const { getRepository } = require('typeorm');
const InventoryEntity = require('./InventoryEntity'); // Adjust the path as necessary

class InventoryRepository {
    async findById(inventoryId) {
        try {
            const repository = getRepository(InventoryEntity);
            return await repository.findOne({ where: { inventoryId } });
        } catch (error) {
            throw new Error(`Error finding inventory by ID: ${error.message}`);
        }
    }

    async findAll() {
        try {
            const repository = getRepository(InventoryEntity);
            return await repository.find();
        } catch (error) {
            throw new Error(`Error finding all inventories: ${error.message}`);
        }
    }

    async create(inventoryData) {
        try {
            const repository = getRepository(InventoryEntity);
            const inventory = repository.create(inventoryData);
            return await repository.save(inventory);
        } catch (error) {
            throw new Error(`Error creating inventory: ${error.message}`);
        }
    }

    async update(inventoryId, inventoryData) {
        try {
            const repository = getRepository(InventoryEntity);
            await repository.update(inventoryId, inventoryData);
            return await this.findById(inventoryId);
        } catch (error) {
            throw new Error(`Error updating inventory: ${error.message}`);
        }
    }

    async delete(inventoryId) {
        try {
            const repository = getRepository(InventoryEntity);
            const result = await repository.delete(inventoryId);
            return result.affected > 0;
        } catch (error) {
            throw new Error(`Error deleting inventory: ${error.message}`);
        }
    }

    async findByFilmId(filmId) {
        try {
            const repository = getRepository(InventoryEntity);
            return await repository.find({ where: { filmId } });
        } catch (error) {
            throw new Error(`Error finding inventories by film ID: ${error.message}`);
        }
    }

    async findByStoreId(storeId) {
        try {
            const repository = getRepository(InventoryEntity);
            return await repository.find({ where: { storeId } });
        } catch (error) {
            throw new Error(`Error finding inventories by store ID: ${error.message}`);
        }
    }
}

module.exports = new InventoryRepository();