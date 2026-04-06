const { Entity, Column, PrimaryGeneratedColumn, ManyToOne, CreateDateColumn, UpdateDateColumn } = require('typeorm');
const { IsNotEmpty } = require('class-validator');

/**
 * Represents an inventory item in the system.
 * This entity tracks the inventory details for films in various stores.
 */
@Entity()
class InventoryEntity {
    /**
     * Unique identifier for the inventory item.
     * @type {number}
     */
    @PrimaryGeneratedColumn()
    inventoryId;

    /**
     * Serial version UID for serialization.
     * @type {number}
     */
    @Column({ type: 'bigint', nullable: true })
    serialVersionUID;

    /**
     * The ID of the film associated with this inventory item.
     * @type {number}
     * @required
     */
    @Column({ type: 'int' })
    @IsNotEmpty()
    filmId;

    /**
     * The ID of the store where this inventory item is located.
     * @type {number}
     * @required
     */
    @Column({ type: 'int' })
    @IsNotEmpty()
    storeId;

    /**
     * The last update timestamp for this inventory item.
     * @type {Date}
     * @required
     */
    @Column({ type: 'timestamp' })
    @IsNotEmpty()
    lastUpdate;

    /**
     * The film associated with this inventory item.
     * @type {FilmEntity}
     * @required
     */
    @ManyToOne(() => FilmEntity, film => film.inventoryItems, { nullable: false })
    filmByFilmId;

    /**
     * The store associated with this inventory item.
     * @type {StoreEntity}
     * @required
     */
    @ManyToOne(() => StoreEntity, store => store.inventoryItems, { nullable: false })
    storeByStoreId;

    /**
     * The timestamp when this inventory item was created.
     * @type {Date}
     */
    @CreateDateColumn()
    createdAt;

    /**
     * The timestamp when this inventory item was last updated.
     * @type {Date}
     */
    @UpdateDateColumn()
    updatedAt;
}

module.exports = InventoryEntity;