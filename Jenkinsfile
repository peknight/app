pipeline {
    agent any
    stages {
        stage('Init') {
            steps {
                sh 'curl "https://git.peknight.com/peknight/build/raw/branch/master/project/build.properties" > project/build.properties'
            }
        }
        stage('Compile') {
            steps {
                sh '''sbt --server 'clean; compile' '''
            }
        }
        stage('Test') {
            steps {
                sh 'sbt --server test'
            }
        }
        stage('Publish Local') {
            steps {
                sh 'sbt --server +publishLocal'
            }
        }
        stage('Publish') {
            steps {
                sh 'sbt --server +publish'
            }
        }
    }
}
