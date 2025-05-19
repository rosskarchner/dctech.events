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

# Container Deployment Changes

## Summary of Changes

The deployment process has been updated to allow specifying container images by URL instead of building them locally. The following changes were made:

1. Added parameters to `template.yaml` for container image URIs
2. Updated Lambda function definitions to use the image URIs from parameters
3. Added conditions to determine whether to use the provided image URIs or build locally
4. Updated `deploy.sh` to accept container image URIs as parameters

## Details

### Before:
- All container images were built locally during deployment using `sam build`
- The `freeze.py` script was run as part of the GitHub Actions workflow

### After:
- Container images can be specified by URL using the new parameters
- Local building is only performed if image URIs are not provided
- The `freeze.py` script is no longer required as part of the GitHub Actions workflow

## Files Changed

1. `template.yaml`: Added parameters for container image URIs and conditions to use them
2. `deploy.sh`: Updated to accept container image URIs as parameters
3. Created `test_ecr_deployment.py`: Tests to verify the changes

## Usage

To deploy using container images from ECR:

```bash
./deploy.sh \
  --aggregator-image 123456789012.dkr.ecr.us-east-1.amazonaws.com/cal-containers-aggregator:latest \
  --api-image 123456789012.dkr.ecr.us-east-1.amazonaws.com/cal-containers-app:latest \
  --static-site-image 123456789012.dkr.ecr.us-east-1.amazonaws.com/cal-containers-app:latest
```

To deploy using locally built images (previous behavior):

```bash
./deploy.sh
```

## Verification

The changes have been verified to ensure:
- The template accepts container image URIs as parameters
- The Lambda functions use the provided image URIs when available
- The deployment script accepts container image URIs as parameters
- Local building is only performed when necessary