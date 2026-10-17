# Operations

## Deployment

Build the container image and deploy it behind a load balancer. One replica is enough for small teams.

## Logging

Logs go to standard output as one JSON object per line. Redirect them to a file if you need to keep them.

## Monitoring

Watch request latency and error rate. A sudden rise in either usually points at a bad deploy.

## Backups

Copy the index directory nightly. Restoring is a matter of putting the directory back and restarting.

## Upgrading

Read the release notes, back up the index, then redeploy the new image. Rollbacks use the previous image.

## Security

Keep API keys in the environment, never in the repository. Rotate a key if it was ever shared.

## Rate limits

Clients are throttled to a fixed number of requests per minute. Retry after a short pause when throttled.

## Troubleshooting

If results look empty, check that the index finished building and that the files are in a supported type.

## Contributing

Open an issue before large changes. Keep pull requests small and include tests.

## Code of conduct

Be kind and assume good intent. Report problems to the maintainers.

## Release process

Tag a release from the main branch, wait for the build to pass, then publish the notes.

## Glossary

Index: the searchable copy of your files. Chunk: one piece of a file that is stored on its own.
