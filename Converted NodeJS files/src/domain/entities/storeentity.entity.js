const { Entity, Column, PrimaryGeneratedColumn, ManyToOne, CreateDateColumn, UpdateDateColumn } = require('typeorm');
const { IsNotEmpty } = require('class-validator');

/**
 * Represents a store entity in the system.
 * This entity holds information about a specific store, including its manager and address.
 */
@Entity('store')
class StoreEntity {
    /**
     * Unique identifier for the store.
     * @type {number}
     */
    @PrimaryGeneratedColumn()
    storeId;

    /**
     * Serial version UID for serialization.
     * @type {number}
     */
    @Column('bigint')
    serialVersionUID;

    /**
     * Identifier for the staff member managing the store.
     * @type {number}
     */
    @Column()
    @IsNotEmpty()
    managerStaffId;

    /**
     * Identifier for the address associated with the store.
     * @type {number}
     */
    @Column()
    @IsNotEmpty()
    addressId;

    /**
     * The last update timestamp for the store entity.
     * @type {Date}
     */
    @Column('timestamp')
    @IsNotEmpty()
    lastUpdate;

    /**
     * Relationship to the StaffEntity representing the manager of the store.
     * @type {StaffEntity}
     */
    @ManyToOne(() => StaffEntity, { nullable: false })
    @IsNotEmpty()
    staffByManagerStaffId;

    /**
     * Relationship to the AddressEntity representing the address of the store.
     * @type {AddressEntity}
     */
    @ManyToOne(() => AddressEntity, { nullable: false })
    @IsNotEmpty()
    addressByAddressId;

    /**
     * Timestamp for when the store entity was created.
     * @type {Date}
     */
    @CreateDateColumn()
    createdAt;

    /**
     * Timestamp for when the store entity was last updated.
     * @type {Date}
     */
    @UpdateDateColumn()
    updatedAt;
}

module.exports = StoreEntity;