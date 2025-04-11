Always suggest a simpler way, if there is one.

Do not offer praise.

Favor using official AWS javascript libraries where it could reduce the amount of code we write.

Rememeber that all API submissions (unless I instruct otherwise) should expect form-encoded input and return HTML output, as we use HTMX. Form encoded might be base64 encoded

We use the Chevron template language.

This IS production code, don't compromise on security


## Renderpage Function

The renderpage function is a Lambda function that generates static HTML pages from Mustache templates. Here's how it works:

1. **Template Discovery**: The function walks through the `pages` directory tree and finds all `.mustache` files.

2. **Rendering Process**:
   - For each template file (e.g., `foo/bar.mustache`), it reads the content and renders it using Chevron.
   - It calculates the output path by replacing the `.mustache` extension with `.html`.
   - For files named `index.mustache`, it places them at the directory level (e.g., `/foo/index.html`).

3. **Dual Output Format**:
   - It creates two versions of each rendered page:
     - A standalone version at `/hx/foo/bar.html` containing just the rendered template content.
     - A shell-wrapped version at `/foo/bar.html` where the content is embedded within the site's shell template.

4. **Shell Template**: The shell template (`templates/shell.mustache`) provides the common HTML structure, including:
   - HTML doctype, head section with meta tags, CSS, and JavaScript
   - Header and navigation elements
   - Footer content
   - The rendered page content is inserted into the shell using the `{{{content}}}` tag.

5. **S3 Storage**: Both versions are uploaded to the specified S3 bucket with appropriate content types.

6. **CloudFront Invalidation**: After rendering all templates, the function creates a CloudFront invalidation to ensure visitors see the latest content immediately.

7. **Deployment Integration**: The function is triggered:
   - Automatically after each CDK deployment via a custom resource
   - Can be manually invoked if needed

8. 

This approach separates content from presentation and enables HTMX to load just the content portions when needed, while providing complete HTML pages for direct navigation.
