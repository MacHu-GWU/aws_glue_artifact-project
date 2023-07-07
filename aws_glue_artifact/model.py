# -*- coding: utf-8 -*-

"""
Todo: add docstring
"""

import typing as T
import dataclasses
from pathlib import Path as _Path

from func_args import NOTHING
from pathlib_mate import Path
from s3pathlib import S3Path
from boto_session_manager import BotoSesManager
from versioned.api import Artifact, Repository, LATEST_VERSION

from .vendor.build import build_python_lib
from .vendor.hashes import hashes


PT = T.Union[str, _Path, Path]


@dataclasses.dataclass
class Base:
    """
    Base class for AWS Glue artifact.
    """
    aws_region: str = dataclasses.field()
    s3_bucket: str = dataclasses.field()
    s3_prefix: str = dataclasses.field()
    dynamodb_table_name: str = dataclasses.field()
    artifact_name: str = dataclasses.field()
    _repo: Repository = dataclasses.field(init=False)

    def _common_post_init(self, suffix: str):
        self._repo = Repository(
            aws_region=self.aws_region,
            s3_bucket=self.s3_bucket,
            s3_prefix=self.s3_prefix,
            dynamodb_table_name=self.dynamodb_table_name,
            suffix=suffix,
        )

    @property
    def repo(self) -> Repository:
        """
        Access the underlying artifact repository object.
        """
        return self._repo

    def bootstrap(
        self,
        bsm: BotoSesManager,
        dynamodb_write_capacity_units: T.Optional[int] = None,
        dynamodb_read_capacity_units: T.Optional[int] = None,
    ):
        """
        Create the required S3 bucket and DynamoDB table for the artifact store backend.
        """
        self.repo.bootstrap(
            bsm=bsm,
            dynamodb_write_capacity_units=dynamodb_write_capacity_units,
            dynamodb_read_capacity_units=dynamodb_read_capacity_units,
        )

    def get_artifact_s3path(
        self,
        version: str = LATEST_VERSION,
    ) -> S3Path:
        """
        Get the S3 path of the versioned artifact.

        :param version: version of the artifact. Default to "LATEST".
        """
        return self.repo.get_artifact_s3path(name=self.artifact_name, version=version)

    def publish_artifact_version(self):
        """
        Publish the latest artifact as an immutable version.
        """
        return self.repo.publish_artifact_version(self.artifact_name)


@dataclasses.dataclass
class GlueETLScriptArtifact(Base):
    """
    AWS Glue ETL Script Artifact.

    :param aws_region: AWS region name of the artifact store.
    :param s3_bucket: S3 bucket name of the artifact store.
    :param s3_prefix: S3 prefix name of the artifact store.
    :param dynamodb_table_name: DynamoDB table name of the artifact store metadata.
    :param artifact_name: Name of the artifact. Eventually, the binary artifact
        will be stored at s3://${s3_bucket}/${s3_prefix}/${artifact_name}/LATEST.py
        the metadata will be stored in ${dynamodb_table_name} DynamoDB table.
    :param path_glue_etl_script: The path of the Glue ETL Python script for artifact.
    """

    path_glue_etl_script: PT = dataclasses.field()

    def __post_init__(self):
        self.path_glue_etl_script = Path(self.path_glue_etl_script).absolute()
        self._common_post_init(suffix=".py")

    def put_artifact(
        self,
        metadata: T.Dict[str, str] = NOTHING,
        tags: T.Dict[str, str] = NOTHING,
    ) -> Artifact:
        """
        Put the artifact to the artifact store.

        :param metadata: Additional custom metadata of the artifact.
        :param tags: Additional custom AWS resource tags of the artifact.
        """
        content = self.path_glue_etl_script.read_bytes()
        glue_etl_script_sha256 = hashes.of_bytes(content)
        final_metadata = {
            "glue_etl_script_sha256": glue_etl_script_sha256,
        }
        if metadata is not NOTHING:
            final_metadata.update(metadata)
        return self.repo.put_artifact(
            name=self.artifact_name,
            content=content,
            content_type="text/plain",
            metadata=final_metadata,
            tags=tags,
        )


@dataclasses.dataclass
class GluePythonLibArtifact(Base):
    """
    AWS Glue Python Library Artifact.

    :param aws_region: AWS region name of the artifact store.
    :param s3_bucket: S3 bucket name of the artifact store.
    :param s3_prefix: S3 prefix name of the artifact store.
    :param dynamodb_table_name: DynamoDB table name of the artifact store metadata.
    :param artifact_name: Name of the artifact. Eventually, the binary artifact
        will be stored at s3://${s3_bucket}/${s3_prefix}/${artifact_name}/LATEST.zip
        the metadata will be stored in ${dynamodb_table_name} DynamoDB table.
    :param dir_glue_python_lib: The directory of the Python library to be built
        for artifact.
    :param dir_glue_build: The temporary directory to store the intermedia
        built artifact. Note that this directory will be removed for reset before
        building the artifact.
    """

    dir_glue_python_lib: PT = dataclasses.field()
    dir_glue_build: PT = dataclasses.field()

    def __post_init__(self):
        self.dir_glue_python_lib = Path(self.dir_glue_python_lib).absolute()
        self.dir_glue_build = Path(self.dir_glue_build).absolute()
        self._common_post_init(suffix=".zip")

    @property
    def dir_glue_python_lib_build(self) -> Path:
        return self.dir_glue_build.joinpath(self.dir_glue_python_lib.basename)

    @property
    def path_glue_python_lib_build_zip(self) -> Path:
        return self.dir_glue_build.joinpath(f"{self.dir_glue_python_lib.basename}.zip")

    def put_artifact(
        self,
        metadata: T.Dict[str, str] = NOTHING,
        tags: T.Dict[str, str] = NOTHING,
    ) -> Artifact:
        """
        Put the artifact to the artifact store.

        :param metadata: Additional custom metadata of the artifact.
        :param tags: Additional custom AWS resource tags of the artifact.
        """
        self.dir_glue_build.remove_if_exists()
        self.dir_glue_build.mkdir_if_not_exists()
        build_python_lib(
            dir_python_lib_source=self.dir_glue_python_lib,
            dir_python_lib_target=self.dir_glue_python_lib_build,
        )
        self.dir_glue_python_lib_build.make_zip_archive(
            dst=self.path_glue_python_lib_build_zip,
            include_dir=False,
        )
        glue_python_lib_sha256 = hashes.of_paths(paths=[self.dir_glue_python_lib_build])
        final_metadata = {
            "glue_python_lib_sha256": glue_python_lib_sha256,
        }
        if metadata is not NOTHING:
            final_metadata.update(metadata)
        return self.repo.put_artifact(
            name=self.artifact_name,
            content=self.path_glue_python_lib_build_zip.read_bytes(),
            content_type="application/zip",
            metadata=final_metadata,
            tags=tags,
        )
