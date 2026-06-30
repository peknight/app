pipeline {
    agent any
    stages {
        stage('Init') {
            steps {
                sh 'curl "https://git.peknight.com/peknight/build/raw/branch/master/project/build.properties" > project/build.properties'
            }
        }
        stage('Build, Test & Publish') {
            steps {
                sh 'sbt --server "clean; testFull; publishLocal; publish; shutdown"'
            }
        }
    }
}