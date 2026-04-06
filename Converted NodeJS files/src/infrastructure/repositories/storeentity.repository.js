const { EntityRepository, Repository } = require('typeorm');
const { StoreEntity } = require('./StoreEntity');

@EntityRepository(StoreEntity)
class StoreRepository extends Repository {
    async findById(storeId) {
        try {
            return await this.findOne({ where: { storeId } });
        } catch (error) {
            throw new Error(`Error finding StoreEntity by ID: ${error.message}`);
        }
    }

    async findAll() {
        try {
            return await this.find();
        } catch (error) {
            throw new Error(`Error finding all StoreEntities: ${error.message}`);
        }
    }

    async createStore(storeData) {
        try {
            const store = this.create(storeData);
            return await this.save(store);
        } catch (error) {
            throw new Error(`Error creating StoreEntity: ${error.message}`);
        }
    }

    async updateStore(storeId, updateData) {
        try {
            await this.update(storeId, updateData);
            return await this.findById(storeId);
        } catch (error) {
            throw new Error(`Error updating StoreEntity: ${error.message}`);
        }
    }

    async deleteStore(storeId) {
        try {
            const result = await this.delete(storeId);
            return result.affected > 0;
        } catch (error) {
            throw new Error(`Error deleting StoreEntity: ${error.message}`);
        }
    }

    async findByManagerStaffId(managerStaffId) {
        try {
            return await this.find({ where: { managerStaffId } });
        } catch (error) {
            throw new Error(`Error finding StoreEntities by managerStaffId: ${error.message}`);
        }
    }

    async findByAddressId(addressId) {
        try {
            return await this.find({ where: { addressId } });
        } catch (error) {
            throw new Error(`Error finding StoreEntities by addressId: ${error.message}`);
        }
    }
}

module.exports = StoreRepository;