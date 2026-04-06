class StoreService {
    constructor(storeRepository, staffRepository, inventoryRepository) {
        this.storeRepository = storeRepository;
        this.staffRepository = staffRepository;
        this.inventoryRepository = inventoryRepository;
    }

    /**
     * Retrieves a paginated list of stores.
     * @param {Object} pageable - Pagination information.
     * @returns {Promise<Array>} - A list of stores.
     */
    async getStoreList(pageable) {
        try {
            return await this.storeRepository.findAll(pageable);
        } catch (error) {
            throw new Error('Error retrieving store list: ' + error.message);
        }
    }

    /**
     * Fetches a store by its unique identifier.
     * @param {number} storeId - The ID of the store.
     * @returns {Promise<StoreDto.Store>} - The store object.
     */
    async getStore(storeId) {
        try {
            const store = await this.storeRepository.findById(storeId);
            if (!store) throw new Error('Store not found');
            return store;
        } catch (error) {
            throw new Error('Error retrieving store: ' + error.message);
        }
    }

    /**
     * Returns a list of detailed information about all stores.
     * @returns {Promise<Array>} - A list of store details.
     */
    async getStoreDetailsList() {
        try {
            return await this.storeRepository.findAllDetails();
        } catch (error) {
            throw new Error('Error retrieving store details list: ' + error.message);
        }
    }

    /**
     * Obtains detailed information about a specific store.
     * @param {number} storeId - The ID of the store.
     * @returns {Promise<StoreDetailsDto.StoreDetails>} - The store details object.
     */
    async getStoreDetails(storeId) {
        try {
            const storeDetails = await this.storeRepository.findDetailsById(storeId);
            if (!storeDetails) throw new Error('Store details not found');
            return storeDetails;
        } catch (error) {
            throw new Error('Error retrieving store details: ' + error.message);
        }
    }

    /**
     * Lists all staff members associated with a specific store.
     * @param {number} storeId - The ID of the store.
     * @returns {Promise<Array>} - A list of staff members.
     */
    async getStoreStaffList(storeId) {
        try {
            return await this.staffRepository.findByStoreId(storeId);
        } catch (error) {
            throw new Error('Error retrieving store staff list: ' + error.message);
        }
    }

    /**
     * Retrieves information about a specific staff member in a store.
     * @param {number} storeId - The ID of the store.
     * @param {number} staffId - The ID of the staff member.
     * @returns {Promise<StaffDto.Staff>} - The staff member object.
     */
    async getStoreStaff(storeId, staffId) {
        try {
            const staff = await this.staffRepository.findByIdAndStoreId(staffId, storeId);
            if (!staff) throw new Error('Staff not found');
            return staff;
        } catch (error) {
            throw new Error('Error retrieving store staff: ' + error.message);
        }
    }

    /**
     * Checks the inventory stock for a specific film in a store.
     * @param {number} storeId - The ID of the store.
     * @param {number} filmId - The ID of the film.
     * @returns {Promise<Array>} - A list of inventory items.
     */
    async checkInventoryStock(storeId, filmId) {
        try {
            return await this.inventoryRepository.checkStock(storeId, filmId);
        } catch (error) {
            throw new Error('Error checking inventory stock: ' + error.message);
        }
    }

    /**
     * Creates and adds a new store to the system.
     * @returns {Promise<StoreDto.Store>} - The created store object.
     */
    async addStore(storeData) {
        try {
            return await this.storeRepository.create(storeData);
        } catch (error) {
            throw new Error('Error adding store: ' + error.message);
        }
    }

    /**
     * Adds a new staff member to a specific store.
     * @param {number} storeId - The ID of the store.
     * @param {number} staffId - The ID of the staff member.
     * @returns {Promise<StaffDto.Staff>} - The added staff member object.
     */
    async addStoreStaff(storeId, staffData) {
        try {
            return await this.staffRepository.addToStore(storeId, staffData);
        } catch (error) {
            throw new Error('Error adding store staff: ' + error.message);
        }
    }

    /**
     * Updates the information of an existing store.
     * @param {number} storeId - The ID of the store.
     * @returns {Promise<StoreDto.Store>} - The updated store object.
     */
    async updateStore(storeId, storeData) {
        try {
            const updatedStore = await this.storeRepository.update(storeId, storeData);
            if (!updatedStore) throw new Error('Store not found for update');
            return updatedStore;
        } catch (error) {
            throw new Error('Error updating store: ' + error.message);
        }
    }

    /**
     * Modifies the details of a specific staff member in a store.
     * @param {number} storeId - The ID of the store.
     * @param {number} staffId - The ID of the staff member.
     * @returns {Promise<StaffDto.Staff>} - The updated staff member object.
     */
    async updateStoreStaff(storeId, staffId, staffData) {
        try {
            const updatedStaff = await this.staffRepository.update(staffId, storeId, staffData);
            if (!updatedStaff) throw new Error('Staff not found for update');
            return updatedStaff;
        } catch (error) {
            throw new Error('Error updating store staff: ' + error.message);
        }
    }

    /**
     * Removes a store from the system using its identifier.
     * @param {number} storeId - The ID of the store.
     */
    async deleteStore(storeId) {
        try {
            await this.storeRepository.delete(storeId);
        } catch (error) {
            throw new Error('Error deleting store: ' + error.message);
        }
    }

    /**
     * Deletes a staff member from a specific store.
     * @param {number} storeId - The ID of the store.
     * @param {number} staffId - The ID of the staff member.
     */
    async removeStoreStaff(storeId, staffId) {
        try {
            await this.staffRepository.removeFromStore(storeId, staffId);
        } catch (error) {
            throw new Error('Error removing store staff: ' + error.message);
        }
    }
}

module.exports = StoreService;