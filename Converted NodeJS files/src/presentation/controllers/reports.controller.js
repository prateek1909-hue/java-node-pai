import { Controller, Get, Route, Tags, SuccessResponse, Response as SwaggerResponse } from 'tsoa';
import { Request, Response, NextFunction } from 'express';
import { validateOrReject } from 'class-validator';

/**
 * @class ReportsController
 * @description This controller handles report generation for sales data.
 * @note Migration from Java ReportsController
 */
@Route('reports/sales')
@Tags('Reports')
export class ReportsController extends Controller {
  
  /**
   * Retrieves sales report categorized by category.
   * @returns {Promise<void>} 200 - Success response
   * @throws {Response} 500 - Internal server error
   */
  @Get('/categories')
  @SuccessResponse('200', 'Success')
  @SwaggerResponse('500', 'Internal Server Error')
  public async reportSalesByCategory(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // Business logic to fetch sales report by category
      // const result = await this.salesService.getSalesByCategory();
      res.status(200).json({ message: 'Sales report by category' });
    } catch (error) {
      this.setStatus(500); // Set the response status to 500
      next(error); // Pass the error to the next middleware
    }
  }

  /**
   * Retrieves sales report categorized by store.
   * @returns {Promise<void>} 200 - Success response
   * @throws {Response} 500 - Internal server error
   */
  @Get('/stores')
  @SuccessResponse('200', 'Success')
  @SwaggerResponse('500', 'Internal Server Error')
  public async reportSalesByStore(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // Business logic to fetch sales report by store
      // const result = await this.salesService.getSalesByStore();
      res.status(200).json({ message: 'Sales report by store' });
    } catch (error) {
      this.setStatus(500); // Set the response status to 500
      next(error); // Pass the error to the next middleware
    }
  }
}