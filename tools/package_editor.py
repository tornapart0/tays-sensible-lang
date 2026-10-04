import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

project = Path(__file__).resolve().parent.parent
editor = project / 'editor'
metadata = json.loads((editor / 'package.json').read_text())
manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{metadata['name']}" Version="{metadata['version']}" Publisher="{metadata['publisher']}" />
    <DisplayName>{metadata['displayName']}</DisplayName>
    <Description xml:space="preserve">{metadata['description']}</Description>
    <Categories>Programming Languages</Categories>
    <Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.85.0" /></Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code" /></Installation>
  <Dependencies />
  <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" /></Assets>
</PackageManifest>
'''
content_types = '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="json" ContentType="application/json" />
<Default Extension="vsixmanifest" ContentType="text/xml" />
</Types>
'''
output = project / 'mylang-syntax.vsix'
with ZipFile(output, 'w', ZIP_DEFLATED) as package:
    package.writestr('extension.vsixmanifest', manifest)
    package.writestr('[Content_Types].xml', content_types)
    for path in sorted(editor.rglob('*')):
        if path.is_file():
            package.write(path, 'extension/' + str(path.relative_to(editor)))
print(output)
