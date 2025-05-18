# ECR Infrastructure Changes

## Summary of Changes

The ECR infrastructure has been updated to match the current container setup. The following changes were made:

1. Renamed `FrontendRepository` to `AppRepository` to better reflect its purpose
2. Removed `AuthenticatedViewsRepository` as it was redundant (had the same name as the App repository)
3. Updated all corresponding outputs to match the new repository names

## Details

### Before:
- `FrontendRepository`: cal-containers-app
- `AggregatorRepository`: cal-containers-aggregator
- `AuthenticatedViewsRepository`: cal-containers-app (duplicate of FrontendRepository)

### After:
- `AppRepository`: cal-containers-app
- `AggregatorRepository`: cal-containers-aggregator

## Files Changed

1. `ecr-infrastructure.yaml`: Updated repository resources and outputs
2. `test_ecr_infrastructure.py`: Updated tests to match the new repository structure
3. Created `verify_fix.py`: Script to verify the changes

## Verification

The changes have been verified to ensure:
- The ECR infrastructure template has the correct repositories
- Repository names match the current container setup
- No duplicate repositories exist
- All outputs are correctly updated

These changes ensure that the ECR infrastructure matches the current container setup, which consists of:
1. An app container (cal-containers-app)
2. An aggregator lambda container (cal-containers-aggregator)