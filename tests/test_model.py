# -*- coding: utf-8 -*-

import moto

from aws_glue_artifact.paths import dir_project_root
from aws_glue_artifact.tests.mock_aws import BaseMockTest

from aws_glue_artifact.model import (
    GlueETLScriptArtifact,
    GluePythonLibArtifact,
)


class Test(BaseMockTest):
    use_mock = True

    mock_list = [
        moto.mock_sts,
        moto.mock_s3,
        moto.mock_dynamodb,
    ]

    def _test(self):
        aws_region = "us-east-1"
        s3_bucket = "my-bucket"
        s3_prefix = "glue-artifact"
        dynamodb_table_name = "glue-artifact"

        glue_etl_script_artifact = GlueETLScriptArtifact(
            aws_region=aws_region,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            dynamodb_table_name=dynamodb_table_name,
            artifact_name="glue_etl_script_1",
            path_glue_etl_script=__file__,
        )
        glue_etl_script_artifact.bootstrap(bsm=self.bsm)
        glue_etl_script_artifact.put_artifact(metadata={"foo": "bar"})
        s3path = glue_etl_script_artifact.get_artifact_s3path()
        assert s3path.uri == f"s3://{s3_bucket}/{s3_prefix}/glue_etl_script_1/LATEST.py"
        glue_etl_script_artifact.publish_artifact_version()

        glue_python_lib_artifact = GluePythonLibArtifact(
            aws_region=aws_region,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            dynamodb_table_name=dynamodb_table_name,
            artifact_name="glue_python_lib",
            dir_glue_python_lib=dir_project_root.joinpath("aws_glue_artifact"),
            dir_glue_build=dir_project_root.joinpath("build", "glue"),
        )
        glue_python_lib_artifact.bootstrap(bsm=self.bsm)
        glue_python_lib_artifact.put_artifact(metadata={"foo": "bar"})
        s3path = glue_python_lib_artifact.get_artifact_s3path()
        assert s3path.uri == f"s3://{s3_bucket}/{s3_prefix}/glue_python_lib/LATEST.zip"
        glue_python_lib_artifact.publish_artifact_version()

    def test(self):
        self._test()


if __name__ == "__main__":
    from aws_glue_artifact.tests import run_cov_test

    run_cov_test(__file__, "aws_glue_artifact.model", preview=False)
