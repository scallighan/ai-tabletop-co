CREATE TABLE PurchaseOrderLines (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    PONumber VARCHAR(50) NOT NULL,
    CustomerName VARCHAR(200) NOT NULL,
    Description VARCHAR(500),
    ProductCode VARCHAR(50),
    Quantity DECIMAL(10,2),
    QuantityUnit VARCHAR(50),
    UnitPrice DECIMAL(10,2),
    TaxAmount DECIMAL(10,2),
    TaxRate DECIMAL(5,4),
    LineTotal DECIMAL(12,2),
    SubtotalAmount DECIMAL(12,2),
    TotalTaxAmount DECIMAL(12,2),
    TotalAmount DECIMAL(12,2)
);
